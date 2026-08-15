"""
Main FastAPI Application Gateway & MCP Protocol 2026-07-28 Streamable HTTP Handler
"""
import time
import json
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from sse_starlette.sse import EventSourceResponse
from config import settings
from security import verify_api_key, check_rate_limit
from logging_obs import logger, metrics
from mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call, WebSearchInput, FetchUrlInput, ExtractMarkdownInput
from mcp_protocol import process_mcp_jsonrpc_request, MCP_PROTOCOL_VERSION
from web_engine import execute_web_search, execute_fetch_url, execute_extract_markdown

app = FastAPI(
    title="MCP Web Engine & Search Gateway",
    description="High-performance, SSRF-hardened MCP Server (Spec 2026-07-28 Streamable HTTP & JSON-RPC 2.0)",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.ENV, "searxng_url": settings.SEARXNG_URL, "mcp_version": MCP_PROTOCOL_VERSION}

@app.get("/v1/metrics")
async def get_metrics(api_key: str = Depends(verify_api_key)):
    return metrics.get_summary()

# Official MCP 2026-07-28 Streamable HTTP Endpoint (JSON-RPC 2.0 POST)
@app.post("/v1/mcp")
async def mcp_streamable_http_endpoint(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    check_rate_limit(api_key)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_JSON", "message": "Request body must be valid JSON-RPC 2.0."}
        )

    res_body, http_status = await process_mcp_jsonrpc_request(payload)
    
    headers = {
        "Mcp-Version": MCP_PROTOCOL_VERSION,
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "Content-Type": "application/json"
    }
    
    return Response(
        content=json.dumps(res_body, ensure_ascii=False) if res_body else "",
        status_code=http_status,
        headers=headers
    )

# Official MCP 2026-07-28 SSE Stream Endpoint (GET)
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
        metrics.record(tool_name, lat, success=True)
        return {"tool": tool_name, "status": "success", "result": res}
    except HTTPException as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False)
        raise e
    except Exception as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
