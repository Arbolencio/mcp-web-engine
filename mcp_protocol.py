"""
MCP Protocol Handler:
- 2026-07-28: Pure Stateless Core (server/discover, tools/list, tools/call) - NO sessions / NO initialize.
- 2025-11-25: Legacy Stateful Protocol (initialize, notifications/initialized, Mcp-Session-Id).
"""
import json
import time
import secrets
from typing import Optional
from fastapi import status
from mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call
from logging_obs import logger, metrics

MCP_PROTOCOL_VERSION_2026 = "2026-07-28"
MCP_PROTOCOL_VERSION_LEGACY = "2025-11-25"

# Legacy 2025-11-25 Sessions Store ONLY
legacy_sessions = {}

# JSON-RPC 2.0 Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

def make_jsonrpc_response(request_id, result):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }

def make_jsonrpc_error(request_id, code, message, data=None):
    err_obj = {"code": code, "message": message}
    if data:
        err_obj["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": err_obj
    }

async def process_mcp_2026_stateless(payload: dict) -> tuple[dict, int]:
    """
    Pure Stateless MCP 2026-07-28 Specification Handler.
    Zero sessions, zero state, zero initialize required.
    Methods: server/discover, tools/list, tools/call.
    """
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return make_jsonrpc_error(payload.get("id") if isinstance(payload, dict) else None, INVALID_REQUEST, "Invalid JSON-RPC 2.0 request."), status.HTTP_400_BAD_REQUEST

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {})

    # 1. server/discover Metadata Discovery
    if method == "server/discover":
        res_data = {
            "protocolVersion": MCP_PROTOCOL_VERSION_2026,
            "server": {
                "name": "mcp-web-engine",
                "version": "1.0.0"
            },
            "capabilities": {
                "tools": True
            }
        }
        return make_jsonrpc_response(request_id, res_data), status.HTTP_200_OK

    # 2. tools/list Discovery
    elif method == "tools/list":
        res_data = {
            "tools": MCP_TOOL_DEFINITIONS
        }
        return make_jsonrpc_response(request_id, res_data), status.HTTP_200_OK

    # 3. tools/call Execution
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return make_jsonrpc_error(request_id, INVALID_PARAMS, "Missing tool 'name' in params."), status.HTTP_400_BAD_REQUEST

        start_t = time.time()
        try:
            raw_result = await handle_mcp_tool_call(tool_name, arguments)
            lat = round((time.time() - start_t) * 1000, 2)
            metrics.record(tool_name, lat, success=True)

            content_text = json.dumps(raw_result, indent=2, ensure_ascii=False)
            mcp_result = {
                "content": [
                    {
                        "type": "text",
                        "text": content_text
                    }
                ],
                "isError": False
            }
            return make_jsonrpc_response(request_id, mcp_result), status.HTTP_200_OK

        except Exception as e:
            lat = round((time.time() - start_t) * 1000, 2)
            metrics.record(tool_name, lat, success=False)
            logger.error(f"Error executing MCP tool '{tool_name}': {str(e)}")

            error_content = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing tool '{tool_name}': {str(e)}"
                    }
                ],
                "isError": True
            }
            return make_jsonrpc_response(request_id, error_content), status.HTTP_200_OK

    # 4. Method Not Found
    else:
        return make_jsonrpc_error(request_id, METHOD_NOT_FOUND, f"Method '{method}' not supported in MCP 2026-07-28 stateless core."), status.HTTP_404_NOT_FOUND

async def process_mcp_2025_legacy_stateful(payload: dict, session_id: Optional[str] = None) -> tuple[dict, int, str]:
    """
    Legacy 2025-11-25 Stateful MCP Protocol Handler.
    Supports initialize, notifications/initialized, and Mcp-Session-Id tracking.
    """
    if session_id and session_id in legacy_sessions:
        current_sess_id = session_id
    else:
        current_sess_id = f"mcp_sess_legacy_{secrets.token_hex(8)}"
        legacy_sessions[current_sess_id] = {"created": time.time()}

    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return make_jsonrpc_error(payload.get("id") if isinstance(payload, dict) else None, INVALID_REQUEST, "Invalid JSON-RPC 2.0 request."), status.HTTP_400_BAD_REQUEST, current_sess_id

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {})

    if method == "initialize":
        res_data = {
            "protocolVersion": MCP_PROTOCOL_VERSION_LEGACY,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "mcp-web-engine-legacy", "version": "1.0.0"}
        }
        return make_jsonrpc_response(request_id, res_data), status.HTTP_200_OK, current_sess_id

    elif method == "notifications/initialized":
        return {}, status.HTTP_202_ACCEPTED, current_sess_id

    elif method == "tools/list":
        return make_jsonrpc_response(request_id, {"tools": MCP_TOOL_DEFINITIONS}), status.HTTP_200_OK, current_sess_id

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            raw_result = await handle_mcp_tool_call(tool_name, arguments)
            mcp_result = {"content": [{"type": "text", "text": json.dumps(raw_result)}], "isError": False}
            return make_jsonrpc_response(request_id, mcp_result), status.HTTP_200_OK, current_sess_id
        except Exception as e:
            return make_jsonrpc_response(request_id, {"content": [{"type": "text", "text": str(e)}], "isError": True}), status.HTTP_200_OK, current_sess_id

    else:
        return make_jsonrpc_error(request_id, METHOD_NOT_FOUND, f"Method '{method}' not found."), status.HTTP_404_NOT_FOUND, current_sess_id
