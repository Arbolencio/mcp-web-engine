"""
Comprehensive Security & MCP 2026-07-28 JSON-RPC 2.0 Test Suite (pytest) for MCP Web Engine
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

# --- OFFICIAL MCP 2026-07-28 SPEC TESTS ---

def test_mcp_2026_initialize():
    payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2026-07-28"
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 0
    assert data["result"]["protocolVersion"] == "2026-07-28"

def test_mcp_2026_tools_list():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.headers.get("Mcp-Version") == "2026-07-28"
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    tools = data["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "web_search" in tool_names
    assert "fetch_url" in tool_names
    assert "extract_markdown" in tool_names

def test_mcp_2026_tools_call_web_search():
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": {"query": "Python", "limit": 3}
        }
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 2
    content = data["result"]["content"]
    assert len(content) > 0
    assert content[0]["type"] == "text"
    parsed_inner = json.loads(content[0]["text"])
    assert "results" in parsed_inner

def test_mcp_2026_tools_call_fetch_url():
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "fetch_url",
            "arguments": {"url": "https://news.ycombinator.com"}
        }
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    content = data["result"]["content"]
    parsed_inner = json.loads(content[0]["text"])
    assert parsed_inner["status_code"] == 200

def test_mcp_2026_tools_call_extract_markdown():
    payload = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "extract_markdown",
            "arguments": {"url": "https://news.ycombinator.com"}
        }
    }
    res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    content = data["result"]["content"]
    parsed_inner = json.loads(content[0]["text"])
    assert "markdown" in parsed_inner

def test_mcp_2026_tool_error():
    payload = {
        "jsonrpc": "2.0",
        "id": 5,
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

# --- SECURITY & SSRF AUDIT TESTS ---

def test_ssrf_protection_basic():
    ssrf_targets = [
        "http://127.0.0.1:8082",
        "http://localhost:5000",
        "http://192.168.1.1",
        "http://169.254.169.254/latest/meta-data/"
    ]
    for target in ssrf_targets:
        payload = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": "fetch_url", "arguments": {"url": target}}
        }
        res = client.post("/v1/mcp", headers=AUTH_HEADERS, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["result"]["isError"] == True
        assert "SSRF_BLOCKED" in data["result"]["content"][0]["text"] or "blocked" in data["result"]["content"][0]["text"].lower()

def test_rate_limit():
    orig_limit = settings.RATE_LIMIT_PER_MINUTE
    settings.RATE_LIMIT_PER_MINUTE = 3
    valid_key = f"Bearer {settings.API_KEY}"
    rate_limit_records.clear()

    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    for _ in range(3):
        res = client.post("/v1/mcp", headers={"Authorization": valid_key}, json=payload)
        assert res.status_code == 200

    res_blocked = client.post("/v1/mcp", headers={"Authorization": valid_key}, json=payload)
    assert res_blocked.status_code == 429

    settings.RATE_LIMIT_PER_MINUTE = orig_limit
