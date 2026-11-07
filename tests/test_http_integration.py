"""Integration regression coverage for all authenticated HTTP paths."""
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from mcp_web_engine import main, security
from mcp_web_engine.config import settings
from mcp_web_engine.mcp_protocol import process_mcp_2025_legacy_stateful, process_mcp_2026_stateless

MASTER = 'synthetic-master-' + 'x' * 40
BETA = 'sk_mcp_beta_synthetic_' + 'b' * 40


@pytest.fixture
def http(monkeypatch, tmp_path):
    path = tmp_path / 'beta_keys.json'
    path.write_text(json.dumps({BETA: {'id': 'synthetic-beta', 'status': 'active', 'limit': 100, 'rate_limit': 120, 'telemetry': {'requests': 0}}}))
    monkeypatch.setattr(settings, 'API_KEY', MASTER)
    monkeypatch.setattr(security, 'BETA_KEYS_FILE', str(path))
    monkeypatch.setenv('MCP_WEB_ENGINE_BETA_KEYS_FILE', str(path))
    monkeypatch.setenv('MCP_WEB_ENGINE_STATE_DB', str(tmp_path / 'usage.sqlite3'))
    security.rate_limit_records.clear()
    monkeypatch.setattr('mcp_web_engine.mcp_tools.execute_web_search', AsyncMock(return_value={'count': 0, 'results': []}))
    monkeypatch.setattr('mcp_web_engine.mcp_tools.execute_extract_markdown', AsyncMock(return_value={'markdown': 'fixture'}))
    return TestClient(main.app)


def auth(key=MASTER):
    return {'Authorization': f'Bearer {key}'}


@pytest.mark.parametrize('path', ['/v1/metrics', '/v1/beta/telemetry'])
def test_beta_cannot_read_operator_aggregates(http, path):
    assert http.get(path, headers=auth(BETA)).status_code == 403
    assert http.get(path, headers=auth()).status_code == 200


@pytest.mark.parametrize('payload', [[], 1, None, {'jsonrpc': '2.0', 'id': {}, 'method': 'tools/list'}, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': None}])
def test_bad_envelopes_never_return_500(http, payload):
    response = http.post('/v1/mcp', headers={**auth(), 'Mcp-Method': 'tools/list'}, json=payload)
    assert response.status_code == 400


@pytest.mark.parametrize('endpoint', ['/v1/mcp', '/v1/mcp/legacy'])
def test_http_notification_has_no_rpc_response(http, endpoint):
    response = http.post(endpoint, headers={**auth(), 'Mcp-Method': 'tools/list'}, json={'jsonrpc': '2.0', 'method': 'tools/list'})
    assert response.status_code == 202
    assert response.content == b''


@pytest.mark.parametrize('processor', [process_mcp_2025_legacy_stateful, process_mcp_2026_stateless])
@pytest.mark.asyncio
async def test_tool_validation_returns_invalid_params_not_secrets(processor):
    response = await processor({'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'web_search', 'arguments': {'query': 'SENSITIVE-QUERY-' * 1000}}})
    assert response[0]['error']['code'] == -32602
    assert 'SENSITIVE-QUERY' not in json.dumps(response)


@pytest.mark.parametrize('processor', [process_mcp_2025_legacy_stateful, process_mcp_2026_stateless])
@pytest.mark.asyncio
async def test_unknown_tool_is_protocol_error(processor):
    response = await processor({'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'nonexistent', 'arguments': {}}})
    assert response[0]['error']['code'] == -32602


def test_quota_shared_across_transports(http, monkeypatch):
    from pathlib import Path
    path = Path(security.BETA_KEYS_FILE)
    record = json.loads(path.read_text())
    record[BETA]['limit'] = 2
    path.write_text(json.dumps(record))
    assert http.post('/v1/search', headers=auth(BETA), json={'query': 'fixture'}).status_code == 200
    assert http.post('/v1/mcp/invoke', headers=auth(BETA), json={'tool': 'web_search', 'arguments': {'query': 'fixture'}}).status_code == 200
    assert http.post('/v1/mcp/legacy', headers=auth(BETA), json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}).status_code in (401, 429)


def test_legacy_session_not_shared_between_principals(http):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}}
    first = http.post('/v1/mcp/legacy', headers=auth(), json=payload)
    sid = first.headers['Mcp-Session-Id']
    second = http.post('/v1/mcp/legacy', headers={**auth(BETA), 'Mcp-Session-Id': sid}, json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    assert second.headers.get('Mcp-Session-Id') != sid


def test_admin_telemetry_keeps_legacy_usage_baseline(http):
    from pathlib import Path
    path = Path(security.BETA_KEYS_FILE)
    data = json.loads(path.read_text())
    data[BETA]['telemetry']['requests'] = 12
    path.write_text(json.dumps(data))
    result = http.get('/v1/beta/telemetry', headers=auth())
    assert result.json()['telemetry']['synthetic-beta']['telemetry']['admissions'] == 12
