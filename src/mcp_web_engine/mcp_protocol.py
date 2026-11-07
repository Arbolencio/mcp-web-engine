"""JSON-RPC handlers. The custom stateless API is retained for compatibility;
its extensions are not claimed to be a certified official MCP implementation.
"""
import asyncio
import hashlib
import json
import secrets
import time
from typing import NoReturn, Optional

from fastapi import HTTPException
from pydantic import ValidationError

from . import __version__
from .logging_obs import logger, metrics
from .mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call

MCP_PROTOCOL_VERSION_2026 = '2026-07-28'
MCP_PROTOCOL_VERSION_LEGACY = '2025-11-25'
REGISTERED_TOOL_NAMES = {t['name'] for t in MCP_TOOL_DEFINITIONS}
VALID_2026_METHODS = {'server/discover', 'tools/list', 'tools/call', 'ping'}
legacy_sessions = {}
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603


def make_jsonrpc_response(request_id, result):
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def make_jsonrpc_error(request_id, code, message, data=None):
    error = {'code': code, 'message': message}
    if data is not None:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': request_id, 'error': error}


def validate_rpc_envelope(payload):
    if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0':
        return make_jsonrpc_error(None, INVALID_REQUEST, 'Invalid JSON-RPC 2.0 request.')
    request_id = payload.get('id')
    if request_id is not None and (isinstance(request_id, bool) or not isinstance(request_id, (str, int))):
        return make_jsonrpc_error(None, INVALID_REQUEST, 'Invalid request id.')
    if not isinstance(payload.get('method'), str) or not payload['method']:
        return make_jsonrpc_error(None, INVALID_REQUEST, 'Missing or invalid method.')
    if not isinstance(payload.get('params', {}), dict):
        return make_jsonrpc_error(request_id, INVALID_PARAMS, 'Params must be an object.')
    if payload['method'] == 'tools/call':
        params = payload.get('params', {})
        if not isinstance(params.get('name'), str) or not params['name'] or not isinstance(params.get('arguments', {}), dict):
            return make_jsonrpc_error(request_id, INVALID_PARAMS, 'A tool name and object arguments are required.')
    return None


def validate_2026_mcp_headers(header_mcp_version: Optional[str], header_mcp_method: Optional[str], header_mcp_name: Optional[str], payload):
    error = validate_rpc_envelope(payload)
    if error:
        raise HTTPException(400, detail=error['error'])

    def fail(code, message) -> NoReturn:
        raise HTTPException(400, detail={'error': code, 'message': message})

    if header_mcp_version and header_mcp_version != MCP_PROTOCOL_VERSION_2026:
        fail('INVALID_PROTOCOL_VERSION', 'Unsupported protocol version.')
    if not header_mcp_method:
        fail('MISSING_MCP_METHOD', "Header 'Mcp-Method' is required.")
    method = header_mcp_method.strip()
    if method not in VALID_2026_METHODS:
        fail('INVALID_MCP_METHOD', 'Unsupported method header.')
    if method != payload['method']:
        fail('MISMATCHED_MCP_METHOD', 'Method header does not match body.')
    if method == 'tools/call':
        if not header_mcp_name:
            fail('MISSING_MCP_NAME', "Header 'Mcp-Name' is required for tools/call.")
        if header_mcp_name.strip() not in REGISTERED_TOOL_NAMES:
            fail('INVALID_MCP_NAME', 'Tool is not registered.')
        if header_mcp_name.strip() != payload['params']['name']:
            fail('MISMATCHED_MCP_NAME', 'Tool header does not match body.')


async def _tool_result(request_id, params, api_key):
    name = params['name']
    if name not in REGISTERED_TOOL_NAMES:
        return make_jsonrpc_error(request_id, INVALID_PARAMS, 'Unknown tool.'), 400
    start = time.monotonic()
    success = False
    try:
        raw = await handle_mcp_tool_call(name, params.get('arguments', {}))
        success = not (isinstance(raw, dict) and raw.get('error'))
        result = {'content': [{'type': 'text', 'text': json.dumps(raw, ensure_ascii=False)}], 'isError': not success}
        return make_jsonrpc_response(request_id, result), 200
    except ValidationError:
        return make_jsonrpc_error(request_id, INVALID_PARAMS, 'Invalid tool arguments.'), 400
    except Exception as exc:
        text = 'Tool execution failed.'
        if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
            code = exc.detail.get('error')
            if isinstance(code, str) and code.isupper() and code.replace('_', '').isalpha() and len(code) <= 64:
                text += ' ' + code
        logger.error('MCP tool execution failed', extra={'extra_data': {'tool': name, 'exception_type': type(exc).__name__}})
        return make_jsonrpc_response(request_id, {'content': [{'type': 'text', 'text': text}], 'isError': True}), 200
    finally:
        await asyncio.to_thread(metrics.record, name, round((time.monotonic() - start) * 1000, 2), success=success, api_key=api_key)


def is_rpc_notification(payload):
    return (isinstance(payload, dict) and payload.get('jsonrpc') == '2.0'
            and isinstance(payload.get('method'), str) and bool(payload['method'])
            and 'id' not in payload)


async def process_mcp_2026_stateless(payload, api_key: Optional[str] = None):
    if is_rpc_notification(payload):
        return {}, 202
    error = validate_rpc_envelope(payload)
    if error:
        return error, 400
    if 'id' not in payload:
        return {}, 202
    request_id, method = payload.get('id'), payload['method']
    if method == 'ping':
        return make_jsonrpc_response(request_id, {}), 200
    if method == 'server/discover':
        return make_jsonrpc_response(request_id, {'protocolVersion': MCP_PROTOCOL_VERSION_2026, 'server': {'name': 'mcp-web-engine', 'version': __version__}, 'capabilities': {'tools': True}}), 200
    if method == 'tools/list':
        return make_jsonrpc_response(request_id, {'tools': MCP_TOOL_DEFINITIONS, 'cacheScope': 'global', 'ttlMs': 3600000, 'listChanged': False}), 200
    if method == 'tools/call':
        return await _tool_result(request_id, payload['params'], api_key)
    return make_jsonrpc_error(request_id, METHOD_NOT_FOUND, 'Method not found.'), 404


async def process_mcp_2025_legacy_stateful(payload, session_id: Optional[str] = None, api_key: Optional[str] = None):
    if is_rpc_notification(payload):
        return {}, 202, ''
    error = validate_rpc_envelope(payload)
    if error:
        return error, 400, ''
    if 'id' not in payload:
        return {}, 202, ''
    now = time.monotonic()
    owner = hashlib.sha256((api_key or 'local-stdio').encode()).hexdigest()
    for key in list(legacy_sessions):
        if now - legacy_sessions[key]['created'] >= 3600:
            del legacy_sessions[key]
    session = legacy_sessions.get(session_id)
    if session is None or session['owner'] != owner:
        session_id = ''
    request_id, method = payload.get('id'), payload['method']
    params = payload.get('params', {})
    if method == 'initialize':
        if not session_id:
            if len(legacy_sessions) >= 1024:
                del legacy_sessions[next(iter(legacy_sessions))]
            session_id = 'mcp_sess_legacy_' + secrets.token_hex(16)
            legacy_sessions[session_id] = {'created': now, 'owner': owner}
        supported = {'2024-11-05', '2025-03-26', '2025-06-18', MCP_PROTOCOL_VERSION_LEGACY}
        version = params.get('protocolVersion')
        version = version if isinstance(version, str) and version in supported else MCP_PROTOCOL_VERSION_LEGACY
        result = {'protocolVersion': version, 'capabilities': {'tools': {'listChanged': False}}, 'serverInfo': {'name': 'mcp-web-engine', 'version': __version__}}
        return make_jsonrpc_response(request_id, result), 200, session_id
    if method == 'ping':
        return make_jsonrpc_response(request_id, {}), 200, session_id
    if method == 'tools/list':
        return make_jsonrpc_response(request_id, {'tools': MCP_TOOL_DEFINITIONS}), 200, session_id
    if method == 'tools/call':
        result, http_status = await _tool_result(request_id, params, api_key)
        return result, http_status, session_id
    return make_jsonrpc_error(request_id, METHOD_NOT_FOUND, 'Method not found.'), 404, session_id
