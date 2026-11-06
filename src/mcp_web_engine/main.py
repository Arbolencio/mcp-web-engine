"""
Main FastAPI Application Gateway & MCP Protocol Handler (SSE & STDIO Modes)
"""
import asyncio
import json
import os
import sys
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from . import __version__
from . import security as security_module
from .config import settings
from .logging_obs import metrics
from .mcp_protocol import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    MCP_PROTOCOL_VERSION_2026,
    MCP_PROTOCOL_VERSION_LEGACY,
    PARSE_ERROR,
    is_rpc_notification,
    make_jsonrpc_error,
    process_mcp_2025_legacy_stateful,
    process_mcp_2026_stateless,
    validate_2026_mcp_headers,
    validate_rpc_envelope,
)
from .mcp_tools import (
    MCP_TOOL_DEFINITIONS,
    ExtractMarkdownInput,
    WebSearchInput,
    handle_mcp_tool_call,
)
from .resource_limits import RequestSizeLimitMiddleware
from .security import check_rate_limit, verify_api_key, verify_master_api_key
from .state_store import StateUnavailable

app = FastAPI(
    title="MCP Web Engine & Search Gateway",
    description="Self-hostable search, public-page fetch and Markdown extraction. Stdio and HTTP transports.",
    version=__version__
)

app.add_middleware(RequestSizeLimitMiddleware)

def _reject_non_finite(value):
    raise ValueError("Non-finite JSON number")


def _load_json(value):
    return json.loads(value, parse_constant=_reject_non_finite)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.ENV,

        "mcp_version": MCP_PROTOCOL_VERSION_2026
    }

@app.get("/v1/metrics")
async def get_metrics(api_key: str = Depends(verify_master_api_key)):
    check_rate_limit(api_key)
    return metrics.get_summary()

@app.get("/v1/beta/telemetry")
async def get_beta_telemetry(api_key: str = Depends(verify_master_api_key)):
    check_rate_limit(api_key)
    if not os.path.exists(security_module.BETA_KEYS_FILE):
        return {"users_count": 0, "telemetry": {}}
    try:
        with open(security_module.BETA_KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        summary = {}
        for k, v in keys.items():
            beta_id = v.get("id", "Unknown")
            usage = metrics.get_beta_telemetry(k)
            baseline = v.get("telemetry", {}).get("requests", 0)
            if type(baseline) is not int or baseline < 0:
                raise ValueError("Invalid legacy usage baseline")
            usage["admissions"] = usage["requests"] = max(baseline, usage["admissions"])
            summary[beta_id] = {
                "id": beta_id,
                "status": v.get("status"),
                "limit": v.get("limit"),
                "telemetry": usage
            }
        return {"users_count": len(summary), "telemetry": summary}
    except (OSError, ValueError, TypeError, AttributeError, StateUnavailable):
        raise HTTPException(status_code=503, detail={"error": "TELEMETRY_UNAVAILABLE"}) from None

# Custom stateless HTTP compatibility endpoint (POST /v1/mcp).
@app.post("/v1/mcp")
async def mcp_2026_stateless_endpoint(
    request: Request,
    api_key: str = Depends(verify_api_key),
    mcp_protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version"),
    mcp_method: Optional[str] = Header(None, alias="Mcp-Method"),
    mcp_name: Optional[str] = Header(None, alias="Mcp-Name")
):
    check_rate_limit(api_key)
    try:
        payload = _load_json(await request.body())
    except Exception:
        return Response(content=json.dumps(make_jsonrpc_error(None, PARSE_ERROR, "Invalid JSON.")), status_code=400, media_type="application/json")

    if is_rpc_notification(payload):
        return Response(status_code=202)
    validate_2026_mcp_headers(mcp_protocol_version, mcp_method, mcp_name, payload)

    res_body, http_status = await process_mcp_2026_stateless(payload, api_key=api_key)
    
    headers = {
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION_2026,
        "Mcp-Method": mcp_method,
        "Content-Type": "application/json"
    }
    if mcp_name:
        headers["Mcp-Name"] = mcp_name
    
    return Response(
        content=json.dumps(res_body, ensure_ascii=False) if res_body else "",
        status_code=http_status,
        headers=headers
    )

# UNCHANGED LEGACY 2025-11-25 STATEFUL ENDPOINT (POST /v1/mcp/legacy)
@app.post("/v1/mcp/legacy")
async def mcp_2025_legacy_endpoint(
    request: Request,
    api_key: str = Depends(verify_api_key),
    mcp_session_id: Optional[str] = Header(None, alias="Mcp-Session-Id")
):
    check_rate_limit(api_key)
    try:
        payload = _load_json(await request.body())
    except Exception:
        return Response(content=json.dumps(make_jsonrpc_error(None, PARSE_ERROR, "Invalid JSON.")), status_code=400, media_type="application/json")

    res_body, http_status, out_session_id = await process_mcp_2025_legacy_stateful(payload, mcp_session_id, api_key=api_key)
    
    headers = {
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION_LEGACY,
        "Mcp-Session-Id": out_session_id,
        "Content-Type": "application/json"
    }
    
    return Response(
        content=json.dumps(res_body, ensure_ascii=False) if res_body else "",
        status_code=http_status,
        headers=headers
    )

# SSE Event Endpoint
@app.get("/v1/mcp")
async def mcp_sse_endpoint(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    check_rate_limit(api_key)

    async def event_generator():
        yield {
            "event": "endpoint",
            "data": "/v1/mcp"
        }

    return EventSourceResponse(event_generator())

# Legacy REST Tool Listing Endpoint (Compatibility)
@app.post("/v1/mcp/tools")
async def list_mcp_tools(api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    return {"tools": MCP_TOOL_DEFINITIONS}

# Legacy REST Tool Invocation Endpoint (Compatibility)
@app.post("/v1/mcp/invoke")
async def invoke_mcp_tool(payload: dict, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    tool_name = payload.get("tool")
    arguments = payload.get("arguments", {})

    if not isinstance(tool_name, str) or tool_name not in {tool['name'] for tool in MCP_TOOL_DEFINITIONS} or not isinstance(arguments, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MISSING_TOOL", "message": "Payload must include 'tool' parameter."}
        )

    start_t = time.time()
    try:
        res = await handle_mcp_tool_call(tool_name, arguments)
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=True, api_key=api_key)
        return {"tool": tool_name, "status": "success", "result": res}
    except ValidationError:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False, api_key=api_key)
        raise HTTPException(400, detail={"error": "INVALID_TOOL_ARGUMENTS"}) from None
    except HTTPException as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False, api_key=api_key)
        raise e
    except Exception:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False, api_key=api_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TOOL_EXECUTION_ERROR", "message": "Tool execution failed."}
        )

# Direct REST Endpoints
@app.post("/v1/search")
async def search_endpoint(body: WebSearchInput, api_key: str = Depends(verify_api_key)):
    result = await invoke_mcp_tool({"tool": "web_search", "arguments": body.model_dump()}, api_key)
    return result["result"]

@app.post("/v1/extract")
async def extract_endpoint(body: ExtractMarkdownInput, api_key: str = Depends(verify_api_key)):
    result = await invoke_mcp_tool({"tool": "extract_markdown", "arguments": body.model_dump()}, api_key)
    return result["result"]

async def run_mcp_stdio_server():
    """Bounded JSON-lines transport. Stdout contains protocol messages only."""
    session_id = None
    while True:
        line = await asyncio.to_thread(sys.stdin.readline, settings.MAX_PAYLOAD_BYTES + 1)
        if not line:
            break
        if len(line.encode("utf-8", errors="surrogatepass")) > settings.MAX_PAYLOAD_BYTES:
            while line and not line.endswith("\n"):
                line = await asyncio.to_thread(sys.stdin.readline, settings.MAX_PAYLOAD_BYTES + 1)
            result = make_jsonrpc_error(None, INVALID_REQUEST, "Message exceeds MAX_PAYLOAD_BYTES.")
        elif not line.strip():
            continue
        else:
            try:
                payload = _load_json(line)
            except (ValueError, RecursionError):
                result = make_jsonrpc_error(None, PARSE_ERROR, "Invalid JSON.")
            else:
                if is_rpc_notification(payload):
                    continue
                result = validate_rpc_envelope(payload)
                if result is None:
                    # Tools are requests, never notifications. Ignore notifications
                    # before dispatch so they cannot cause unacknowledged I/O.
                    if "id" not in payload:
                        continue
                    try:
                        if payload["method"] == "server/discover":
                            result, _ = await process_mcp_2026_stateless(payload, api_key="local-stdio")
                        else:
                            result, _, session_id = await process_mcp_2025_legacy_stateful(payload, session_id, api_key="local-stdio")
                    except Exception:
                        result = make_jsonrpc_error(payload.get("id"), INTERNAL_ERROR, "Internal error.")
        if result:
            sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
            sys.stdout.flush()

def cli_entrypoint():
    """
    Console script entrypoint for PyPI / uvx (mcp-web-engine).
    Runs Stdio MCP mode by default; runs FastAPI HTTP server if --serve is passed.
    """
    is_serve = "--serve" in sys.argv or "--sse" in sys.argv
    if is_serve:
        if len(settings.API_KEY.strip()) < 32:
            raise SystemExit("HTTP mode requires an operator-generated API_KEY of at least 32 characters.")
        import uvicorn
        uvicorn.run("mcp_web_engine.main:app", host=settings.HOST, port=settings.PORT, reload=False)
    else:
        asyncio.run(run_mcp_stdio_server())

if __name__ == "__main__":
    cli_entrypoint()
