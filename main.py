"""
Main FastAPI Application Gateway & MCP Protocol Handler
"""
import time
from fastapi import FastAPI, Depends, HTTPException, status, Security
from config import settings
from security import verify_api_key, check_rate_limit
from logging_obs import logger, metrics
from mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call, WebSearchInput, FetchUrlInput, ExtractMarkdownInput
from web_engine import execute_web_search, execute_fetch_url, execute_extract_markdown

app = FastAPI(
    title="MCP Web Engine & Search Gateway",
    description="High-performance, SSRF-hardened MCP Server & Search/Scraping API Gateway",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.ENV, "searxng_url": settings.SEARXNG_URL}

@app.get("/v1/metrics")
async def get_metrics(api_key: str = Depends(verify_api_key)):
    return metrics.get_summary()

# MCP Protocol Tool Listing Endpoint
@app.post("/v1/mcp/tools")
async def list_mcp_tools(api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    return {"tools": MCP_TOOL_DEFINITIONS}

# MCP Protocol Tool Invocation Endpoint
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
        logger.info(f"MCP tool '{tool_name}' invoked successfully", extra={"extra_data": {"tool": tool_name, "latency_ms": lat}})
        return {"tool": tool_name, "status": "success", "result": res}
    except HTTPException as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False)
        raise e
    except Exception as e:
        lat = round((time.time() - start_t) * 1000, 2)
        metrics.record(tool_name, lat, success=False)
        logger.error(f"Error executing MCP tool '{tool_name}': {str(e)}")
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
