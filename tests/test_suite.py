"""
Comprehensive Test Suite for MCP 2026-07-28 Pure Stateless Core & Legacy 2025-11-25 Stateful Protocol
"""
import pytest
from fastapi.testclient import TestClient
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from config import settings
from security import rate_limit_records

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {settings.API_KEY}"}

def setup_function(function):
    rate_limit_records.clear()

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["mcp_version"] == "2026-07-28"

def test_invalid_api_key():
    res = client.post("/v1/mcp", headers={"Authorization": "Bearer invalid_key_999"}, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert res.status_code == 401

# --- PURE STATELESS MCP 2026-07-28 SPEC TESTS ---

def test_mcp_2026_stateless_discover():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "server/discover",
        "params": {}
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2026-07-28"
    assert "Mcp-Session-Id" not in res.headers  # STRICTLY NO SESSION ID HEADER!
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert data["result"]["protocolVersion"] == "2026-07-28"
    assert data["result"]["server"]["name"] == "mcp-web-engine"

def test_mcp_2026_stateless_tools_list():
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2026-07-28"
    assert "Mcp-Session-Id" not in res.headers
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    tools = data["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "web_search" in tool_names
    assert "fetch_url" in tool_names
    assert "extract_markdown" in tool_names

def test_mcp_2026_stateless_tools_call_web_search():
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": {"query": "Python", "limit": 3}
        }
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2026-07-28"
    assert "Mcp-Session-Id" not in res.headers
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 3
    content = data["result"]["content"]
    assert len(content) > 0
    assert content[0]["type"] == "text"

def test_mcp_2026_stateless_tool_error():
    payload = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "unknown_tool",
            "arguments": {}
        }
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["result"]["isError"] == True

# --- LEGACY 2025-11-25 STATEFUL TESTS ---

def test_mcp_2025_legacy_stateful():
    payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25"}
    }
    res = client.post("/v1/mcp/legacy", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2025-11-25"
    assert "Mcp-Session-Id" in res.headers  # Legacy HAS Session ID
