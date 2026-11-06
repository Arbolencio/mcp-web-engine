"""HTTP and stdio boundary regressions; no outbound requests."""
import asyncio
import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mcp_web_engine import main
from mcp_web_engine.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, 'API_KEY', 'test-key-' + 'x' * 40)
    return TestClient(main.app)


def test_health_hides_internal_endpoint(client):
    data = client.get('/health').json()
    assert 'searxng_url' not in data


def test_http_rejects_oversized_body_before_parsing(client, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_PAYLOAD_BYTES', 64)
    response = client.post('/v1/mcp', content=' ' * 65)
    assert response.status_code == 413


def test_http_rejects_oversized_stream_without_content_length(client, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_PAYLOAD_BYTES', 64)
    response = client.post('/v1/mcp', content=iter([b' ' * 32, b' ' * 33]))
    assert response.status_code == 413


@pytest.mark.parametrize('payload', [[], None, 1, {'jsonrpc': '1.0', 'id': 1, 'method': 'ping'}, {'jsonrpc': '2.0', 'id': [], 'method': 'ping'}, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': []}])
def test_stdio_invalid_envelope_returns_protocol_error(payload):
    stdin = io.StringIO(json.dumps(payload) + '\n')
    stdout = io.StringIO()
    with patch.object(main.sys, 'stdin', stdin), patch.object(main.sys, 'stdout', stdout):
        asyncio.run(main.run_mcp_stdio_server())
    result = json.loads(stdout.getvalue())
    assert result['error']['code'] in (-32600, -32602)


def test_stdio_parse_error_code():
    stdout = io.StringIO()
    with patch.object(main.sys, 'stdin', io.StringIO('{\n')), patch.object(main.sys, 'stdout', stdout):
        asyncio.run(main.run_mcp_stdio_server())
    assert json.loads(stdout.getvalue())['error']['code'] == -32700


def test_stdio_rejects_oversized_message(monkeypatch):
    monkeypatch.setattr(settings, 'MAX_PAYLOAD_BYTES', 64)
    stdout = io.StringIO()
    with patch.object(main.sys, 'stdin', io.StringIO(' ' * 65 + '\n')), patch.object(main.sys, 'stdout', stdout):
        asyncio.run(main.run_mcp_stdio_server())
    assert json.loads(stdout.getvalue())['error']['code'] == -32600


def test_stdio_tool_notification_never_executes():
    stdout = io.StringIO()
    payload = {'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'fetch_url', 'arguments': {'url': 'https://example.com'}}}
    from unittest.mock import AsyncMock
    with patch.object(main.sys, 'stdin', io.StringIO(json.dumps(payload) + '\n')), patch.object(main.sys, 'stdout', stdout), patch('mcp_web_engine.mcp_protocol.handle_mcp_tool_call', new_callable=AsyncMock) as tool:
        asyncio.run(main.run_mcp_stdio_server())
    assert stdout.getvalue() == ''
    tool.assert_not_awaited()
