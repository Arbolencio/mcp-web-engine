"""Protocol edge cases: silent notifications, finite JSON and bounded sessions."""
import asyncio
import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mcp_web_engine import main
from mcp_web_engine.config import settings
from mcp_web_engine.mcp_protocol import legacy_sessions, process_mcp_2025_legacy_stateful


def test_stdio_invalid_notification_params_still_silent():
    output = io.StringIO()
    messages = [{'jsonrpc': '2.0', 'method': 'tools/call', 'params': None}, {'jsonrpc': '2.0', 'id': 9, 'method': 'ping'}]
    with patch.object(main.sys, 'stdin', io.StringIO(''.join(json.dumps(m) + '\n' for m in messages))), patch.object(main.sys, 'stdout', output):
        asyncio.run(main.run_mcp_stdio_server())
    assert [json.loads(line)['id'] for line in output.getvalue().splitlines()] == [9]


@pytest.mark.parametrize('endpoint', ['/v1/mcp', '/v1/mcp/legacy'])
def test_http_parse_error_is_json_rpc(http_client, endpoint):
    response = http_client.post(endpoint, headers={'Authorization': 'Bearer ' + settings.API_KEY}, content='{')
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32700


@pytest.fixture
def http_client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'API_KEY', 'synthetic-' + 'm' * 40)
    monkeypatch.setenv('MCP_WEB_ENGINE_STATE_DB', str(tmp_path / 'usage.sqlite3'))
    return TestClient(main.app)


def test_stdio_non_finite_json_rejected():
    output = io.StringIO()
    with patch.object(main.sys, 'stdin', io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":NaN}}\n')), patch.object(main.sys, 'stdout', output):
        asyncio.run(main.run_mcp_stdio_server())
    assert json.loads(output.getvalue())['error']['code'] == -32700


@pytest.mark.asyncio
async def test_notifications_cannot_grow_sessions():
    legacy_sessions.clear()
    for _ in range(2000):
        await process_mcp_2025_legacy_stateful({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    assert len(legacy_sessions) == 0


@pytest.mark.asyncio
async def test_session_capacity_and_expiry(monkeypatch):
    from mcp_web_engine import mcp_protocol
    legacy_sessions.clear()
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}
    for _ in range(1100):
        await process_mcp_2025_legacy_stateful(request)
    assert len(legacy_sessions) == 1024
    future = mcp_protocol.time.monotonic() + 3601
    monkeypatch.setattr(mcp_protocol.time, 'monotonic', lambda: future)
    await process_mcp_2025_legacy_stateful(request)
    assert len(legacy_sessions) == 1
    legacy_sessions.clear()
