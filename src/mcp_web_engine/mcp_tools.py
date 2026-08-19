"""
MCP Tools Definition & Schema Handlers (web_search, fetch_url, extract_markdown)
"""
from typing import Optional
from pydantic import BaseModel, Field
from .web_engine import execute_web_search, execute_fetch_url, execute_extract_markdown

class WebSearchInput(BaseModel):
    query: str = Field(..., description="The search query keywords", min_length=2)
    limit: Optional[int] = Field(default=10, description="Max results to return (1-25)", ge=1, le=25)

class FetchUrlInput(BaseModel):
    url: str = Field(..., description="Target URL to fetch content from")
    max_bytes: Optional[int] = Field(default=None, description="Max bytes payload limit")

class ExtractMarkdownInput(BaseModel):
    url: str = Field(..., description="Target URL to convert to clean Markdown")
    max_bytes: Optional[int] = Field(default=None, description="Max bytes payload limit")

# MCP Protocol Tool Definitions
MCP_TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Performs aggregate multi-engine web search returning structured search results.",
        "inputSchema": WebSearchInput.model_json_schema()
    },
    {
        "name": "fetch_url",
        "description": "Fetches raw text content of a web page after SSRF security checks.",
        "inputSchema": FetchUrlInput.model_json_schema()
    },
    {
        "name": "extract_markdown",
        "description": "Scrapes a web page and converts HTML into clean, structured Markdown for LLMs.",
        "inputSchema": ExtractMarkdownInput.model_json_schema()
    }
]

async def handle_mcp_tool_call(tool_name: str, arguments: dict):
    if tool_name == "web_search":
        parsed = WebSearchInput(**arguments)
        return await execute_web_search(parsed.query, parsed.limit)
    elif tool_name == "fetch_url":
        parsed = FetchUrlInput(**arguments)
        return await execute_fetch_url(parsed.url, parsed.max_bytes)
    elif tool_name == "extract_markdown":
        parsed = ExtractMarkdownInput(**arguments)
        return await execute_extract_markdown(parsed.url, parsed.max_bytes)
    else:
        raise ValueError(f"Unknown tool name '{tool_name}'")
