"""Whole-project review regressions for CLI, HTTP and resource boundaries."""
import asyncio
import json
import subprocess
import sys
import threading
import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from mcp_web_engine import main
from mcp_web_engine.config import settings
from mcp_web_engine.resource_limits import RequestSizeLimitMiddleware


@pytest.mark.parametrize('flag,expected', [('--help', 'usage:'), ('--version', '1.2.1')])
def test_cli_informational_flags(flag, expected):
    result = subprocess.run([sys.executable, '-m', 'mcp_web_engine.main', flag], input='', capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout


def test_cli_rejects_unknown_flags():
    result = subprocess.run([sys.executable, '-m', 'mcp_web_engine.main', '--typo'], input='', capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert 'unrecognized arguments' in result.stderr


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'API_KEY', 'synthetic-' + 'x' * 40)
    monkeypatch.setenv('MCP_WEB_ENGINE_STATE_DB', str(tmp_path / 'usage.sqlite3'))
    return TestClient(main.app)


@pytest.mark.parametrize('endpoint,headers', [('/v1/mcp', {'Mcp-Method': 'ping'}), ('/v1/mcp/legacy', {})])
def test_http_surrogate_request_id_is_safely_serialized(client, endpoint, headers):
    response = client.post(endpoint, headers={**headers, 'Authorization': 'Bearer ' + settings.API_KEY}, content=json.dumps({'jsonrpc': '2.0', 'id': '\ud800', 'method': 'ping'}))
    assert response.status_code == 200
    assert response.json()['id'] == '\ud800'


@pytest.mark.asyncio
async def test_slow_body_has_a_total_deadline(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('mcp_web_engine.resource_limits.settings', SimpleNamespace(MAX_PAYLOAD_BYTES=1024, REQUEST_BODY_TIMEOUT_SEC=.03, MAX_CONCURRENT_REQUESTS=2))
    messages = []
    async def receive():
        await asyncio.sleep(.2)
        return {'type': 'http.request', 'body': b'', 'more_body': True}
    async def app(scope, receive, send):
        raise AssertionError('Incomplete request must never reach the app')
    started = time.monotonic()
    try:
        await asyncio.wait_for(RequestSizeLimitMiddleware(app)({'type': 'http', 'headers': []}, receive, AsyncMock(side_effect=messages.append)), .1)
    except asyncio.TimeoutError:
        pytest.fail('No request-body deadline; unauthenticated slow body occupies a slot indefinitely')
    assert time.monotonic() - started < .15
    assert messages[0]['status'] == 408


@pytest.mark.asyncio
async def test_database_admission_does_not_block_event_loop(monkeypatch):
    done = threading.Event()
    def slow_check(_):
        time.sleep(.12)
        done.set()
    monkeypatch.setattr(main, 'check_rate_limit', slow_check)
    task = asyncio.create_task(main.list_mcp_tools('synthetic'))
    await asyncio.sleep(.01)
    responsive = not done.is_set()
    await task
    assert responsive, 'SQLite contention blocks the event loop and health checks'


@pytest.mark.asyncio
async def test_rest_does_not_report_backend_failure_as_success(monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(main, 'check_rate_limit', lambda _: None)
    monkeypatch.setattr(main, 'handle_mcp_tool_call', AsyncMock(return_value={'error': 'SEARXNG_UNAVAILABLE', 'results': []}))
    record = Mock()
    monkeypatch.setattr(main.metrics, 'record', record)
    response = await main.invoke_mcp_tool({'tool': 'web_search', 'arguments': {'query': 'fixture'}}, 'synthetic')
    assert response['status'] == 'error'
    assert record.call_args.kwargs['success'] is False

