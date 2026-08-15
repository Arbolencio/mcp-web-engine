"""
Comprehensive Security & Functional Automated Test Suite (pytest) for MCP Web Engine
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

def test_invalid_api_key():
    res = client.post("/v1/mcp/tools", headers={"Authorization": "Bearer invalid_key_999"})
    assert res.status_code == 401
    assert res.json()["detail"]["error"] == "UNAUTHORIZED"

def test_mcp_tools_list():
    res = client.post("/v1/mcp/tools", headers=AUTH_HEADERS)
    assert res.status_code == 200
    tools = res.json()["tools"]
    tool_names = [t["name"] for t in tools]
    assert "web_search" in tool_names
    assert "fetch_url" in tool_names
    assert "extract_markdown" in tool_names

def test_web_search():
    payload = {
        "tool": "web_search",
        "arguments": {"query": "Python", "limit": 5}
    }
    res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["tool"] == "web_search"
    assert data["status"] == "success"

def test_fetch_url():
    payload = {
        "tool": "fetch_url",
        "arguments": {"url": "https://news.ycombinator.com"}
    }
    res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["result"]["status_code"] == 200
    assert data["result"]["content_length"] > 100

def test_extract_markdown():
    payload = {
        "tool": "extract_markdown",
        "arguments": {"url": "https://news.ycombinator.com"}
    }
    res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "markdown" in data["result"]
    assert data["result"]["markdown_length"] > 100

def test_ssrf_protection_basic():
    ssrf_targets = [
        "http://127.0.0.1:8082",
        "http://localhost:5000",
        "http://192.168.1.1",
        "http://169.254.169.254/latest/meta-data/"
    ]
    for target in ssrf_targets:
        payload = {"tool": "fetch_url", "arguments": {"url": target}}
        res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
        assert res.status_code in [400, 403]
        detail = res.json()["detail"]
        assert detail["error"] in ["SSRF_BLOCKED", "MISSING_HOSTNAME", "INVALID_SCHEME", "DNS_RESOLUTION_FAILED"]

def test_ssrf_advanced_bypasses():
    bypass_targets = [
        "http://%31%32%37%2E%30%2E%30%2E%31:8082",
        "http://2130706433:8082",
        "http://admin:secret@127.0.0.1:8082",
        "http://0.0.0.0:8082",
        "http://[::1]:8082"
    ]
    for target in bypass_targets:
        payload = {"tool": "fetch_url", "arguments": {"url": target}}
        res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
        assert res.status_code in [400, 403]
        assert res.json()["detail"]["error"] == "SSRF_BLOCKED"

def test_invalid_url():
    payload = {"tool": "fetch_url", "arguments": {"url": "not_a_valid_url"}}
    res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "INVALID_SCHEME"

def test_rate_limit():
    orig_limit = settings.RATE_LIMIT_PER_MINUTE
    settings.RATE_LIMIT_PER_MINUTE = 3
    valid_key = f"Bearer {settings.API_KEY}"
    rate_limit_records.clear()

    for _ in range(3):
        res = client.post("/v1/mcp/tools", headers={"Authorization": valid_key})
        assert res.status_code == 200

    res_blocked = client.post("/v1/mcp/tools", headers={"Authorization": valid_key})
    assert res_blocked.status_code == 429
    assert res_blocked.json()["detail"]["error"] == "RATE_LIMIT_EXCEEDED"

    settings.RATE_LIMIT_PER_MINUTE = orig_limit

def test_backend_error():
    orig_url = settings.SEARXNG_URL
    settings.SEARXNG_URL = "http://127.0.0.1:9999/invalid_search"
    rate_limit_records.clear()
    payload = {"tool": "web_search", "arguments": {"query": "test error"}}
    res = client.post("/v1/mcp/invoke", headers=AUTH_HEADERS, json=payload)
    assert res.status_code in [502, 503]
    assert res.json()["detail"]["error"] in ["BACKEND_ERROR", "SEARCH_FAILED"]
    settings.SEARXNG_URL = orig_url
