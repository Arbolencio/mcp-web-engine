"""
Main FastAPI Application Gateway & MCP Protocol Handler (SSE & STDIO Modes)
"""
import time
import json
import os
import sys
import asyncio
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request, Header
from typing import Optional
from sse_starlette.sse import EventSourceResponse
from config import settings
from security import verify_api_key, check_rate_limit
from logging_obs import logger, metrics
from mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call, WebSearchInput, FetchUrlInput, ExtractMarkdownInput
from mcp_protocol import (
    process_mcp_2026_stateless,
    process_mcp_2025_legacy_stateful,
    validate_2026_mcp_headers,
    MCP_PROTOCOL_VERSION_2026,
    MCP_PROTOCOL_VERSION_LEGACY
)
from web_engine import execute_web_search, execute_fetch_url, execute_extract_markdown

BETA_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beta_keys.json")

app = FastAPI(
    title="MCP Web Engine & Search Gateway",
    description="High-performance, SSRF-hardened MCP Server (Spec 2026-07-28 Pure Stateless Core & Legacy 2025-11-25)",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.ENV,
        "searxng_url": settings.SEARXNG_URL,
        "mcp_version": MCP_PROTOCOL_VERSION_2026
    }

@app.get("/v1/metrics")
async def get_metrics(api_key: str = Depends(verify_api_key)):
    return metrics.get_summary()

@app.get("/v1/beta/telemetry")
async def get_beta_telemetry(api_key: str = Depends(verify_api_key)):
    if not os.path.exists(BETA_KEYS_FILE):
        return {"users_count": 0, "telemetry": {}}
    try:
        with open(BETA_KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        summary = {}
        for k, v in keys.items():
            beta_id = v.get("id", "Unknown")
            summary[beta_id] = {
                "id": beta_id,
                "status": v.get("status"),
                "limit": v.get("limit"),
                "telemetry": v.get("telemetry", {})
            }
        return {"users_count": len(summary), "telemetry": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# OFFICIAL MCP 2026-07-28 STATELESS CORE ENDPOINT (POST /v1/mcp)
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
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_JSON", "message": "Request body must be valid JSON-RPC 2.0."}
        )

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
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_JSON", "message": "Request body must be valid JSON-RPC 2.0."}
        )

    res_body, http_status, out_session_id = await process_mcp_2025_legacy_stateful(payload, mcp_session_id)
    
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

    if not tool_name:
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
    except HTTPException as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False, api_key=api_key)
        raise e
    except Exception as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False, api_key=api_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TOOL_EXECUTION_ERROR", "message": str(e)}
        )

# Direct REST Endpoints
@app.post("/v1/search")
async def search_endpoint(body: WebSearchInput, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    return await execute_web_search(body.query, body.limit)

@app.post("/v1/extract")
async def extract_endpoint(body: ExtractMarkdownInput, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    return await execute_extract_markdown(body.url, body.max_bytes)

async def run_mcp_stdio_server():
    """
    Stdio MCP protocol handler for CLI executions (e.g. npx -y mcp-web-engine)
    """
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        line_str = line.decode("utf-8").strip()
        if not line_str:
            continue
        try:
            payload = json.loads(line_str)
            res_body, _ = await process_mcp_2026_stateless(payload, api_key="local-stdio")
            if res_body:
                sys.stdout.write(json.dumps(res_body, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    is_stdio = "--stdio" in sys.argv or not sys.stdin.isatty()
    if is_stdio:
        asyncio.run(run_mcp_stdio_server())
    else:
        import uvicorn
        uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
