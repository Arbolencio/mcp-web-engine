"""
Comprehensive Test Suite for Spec 2026-07-28 Header Validation & Cache Metadata
"""
import pytest
from fastapi.testclient import TestClient
import os
import sys

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

# --- HEADER VALIDATION TESTS ---

def test_missing_mcp_method():
    headers = {**AUTH_HEADERS}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "server/discover"}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "MISSING_MCP_METHOD"

def test_invalid_mcp_method():
    headers = {**AUTH_HEADERS, "Mcp-Method": "invalid/method"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "invalid/method"}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "INVALID_MCP_METHOD"

def test_mismatched_mcp_method():
    headers = {**AUTH_HEADERS, "Mcp-Method": "server/discover"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "MISMATCHED_MCP_METHOD"

def test_missing_mcp_name_on_tools_call():
    headers = {**AUTH_HEADERS, "Mcp-Method": "tools/call"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "web_search", "arguments": {"query": "test"}}}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "MISSING_MCP_NAME"

def test_invalid_mcp_name():
    headers = {**AUTH_HEADERS, "Mcp-Method": "tools/call", "Mcp-Name": "unknown_tool"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "unknown_tool", "arguments": {}}}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "INVALID_MCP_NAME"

def test_mismatched_mcp_name():
    headers = {**AUTH_HEADERS, "Mcp-Method": "tools/call", "Mcp-Name": "web_search"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fetch_url", "arguments": {"url": "https://example.com"}}}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "MISMATCHED_MCP_NAME"

# --- SPEC 2026-07-28 VALID SUCCESS TESTS WITH HEADERS & CACHE METADATA ---

def test_discover_with_headers():
    headers = {**AUTH_HEADERS, "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"}
    payload = {"jsonrpc": "2.0", "id": 100, "method": "server/discover", "params": {}}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2026-07-28"
    assert res.headers.get("Mcp-Method") == "server/discover"
    assert res.json()["result"]["protocolVersion"] == "2026-07-28"

def test_tools_list_cache_metadata():
    headers = {**AUTH_HEADERS, "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"}
    payload = {"jsonrpc": "2.0", "id": 101, "method": "tools/list", "params": {}}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 200
    assert res.headers.get("Mcp-Method") == "tools/list"
    res_data = res.json()["result"]
    assert "tools" in res_data
    assert res_data["cacheScope"] == "global"
    assert res_data["ttlMs"] == 3600000
    assert res_data["listChanged"] == False

def test_tools_call_with_headers():
    headers = {**AUTH_HEADERS, "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "web_search"}
    payload = {"jsonrpc": "2.0", "id": 102, "method": "tools/call", "params": {"name": "web_search", "arguments": {"query": "Python", "limit": 2}}}
    res = client.post("/v1/mcp", headers=headers, json=payload)
    assert res.status_code == 200
    assert res.headers.get("Mcp-Method") == "tools/call"
    assert res.headers.get("Mcp-Name") == "web_search"
    assert res.json()["result"]["isError"] == False

def test_legacy_endpoint_unmodified():
    headers = {**AUTH_HEADERS}
    payload = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}
    res = client.post("/v1/mcp/legacy", headers=headers, json=payload)
    assert res.status_code == 200
    assert res.headers.get("MCP-Protocol-Version") == "2025-11-25"
    assert "Mcp-Session-Id" in res.headers
