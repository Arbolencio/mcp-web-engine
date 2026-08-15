"""
MCP Protocol Handler (Spec 2026-07-28 Pure Stateless Core with Header Validation & Cache Metadata)
"""
import json
import time
import secrets
from typing import Optional
from fastapi import status, HTTPException
from mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call
from logging_obs import logger, metrics

MCP_PROTOCOL_VERSION_2026 = "2026-07-28"
MCP_PROTOCOL_VERSION_LEGACY = "2025-11-25"

REGISTERED_TOOL_NAMES = {t["name"] for t in MCP_TOOL_DEFINITIONS}
VALID_2026_METHODS = {"server/discover", "tools/list", "tools/call"}

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

def validate_2026_mcp_headers(
    header_mcp_version: Optional[str],
    header_mcp_method: Optional[str],
    header_mcp_name: Optional[str],
    payload: dict
):
    """
    Validates MCP 2026-07-28 headers and ensures strict correspondence with JSON-RPC body.
    """
    # 1. Validate MCP-Protocol-Version
    if header_mcp_version and header_mcp_version != MCP_PROTOCOL_VERSION_2026:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_PROTOCOL_VERSION", "message": f"Expected 'MCP-Protocol-Version: {MCP_PROTOCOL_VERSION_2026}'."}
        )

    # 2. Validate Mcp-Method Header Presence
    if not header_mcp_method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MISSING_MCP_METHOD", "message": "Header 'Mcp-Method' is required."}
        )

    clean_method = header_mcp_method.strip()
    if clean_method not in VALID_2026_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_MCP_METHOD", "message": f"Method '{clean_method}' is not a valid MCP 2026-07-28 method."}
        )

    body_method = payload.get("method")
    if clean_method != body_method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MISMATCHED_MCP_METHOD", "message": f"Header Mcp-Method '{clean_method}' does not match body method '{body_method}'."}
        )

    # 3. Validate Mcp-Name when method is tools/call
    if clean_method == "tools/call":
        if not header_mcp_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "MISSING_MCP_NAME", "message": "Header 'Mcp-Name' is required for method 'tools/call'."}
            )

        clean_name = header_mcp_name.strip()
        if clean_name not in REGISTERED_TOOL_NAMES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_MCP_NAME", "message": f"Tool '{clean_name}' is not registered."}
            )

        body_tool_name = payload.get("params", {}).get("name")
        if clean_name != body_tool_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "MISMATCHED_MCP_NAME", "message": f"Header Mcp-Name '{clean_name}' does not match body params.name '{body_tool_name}'."}
            )

async def process_mcp_2026_stateless(payload: dict) -> tuple[dict, int]:
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

    # 2. tools/list Discovery with Spec 2026-07-28 Cache Metadata
    elif method == "tools/list":
        res_data = {
            "tools": MCP_TOOL_DEFINITIONS,
            "cacheScope": "global",
            "ttlMs": 3600000,
            "listChanged": False
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

    else:
        return make_jsonrpc_error(request_id, METHOD_NOT_FOUND, f"Method '{method}' not supported in MCP 2026-07-28 stateless core."), status.HTTP_404_NOT_FOUND

async def process_mcp_2025_legacy_stateful(payload: dict, session_id: Optional[str] = None) -> tuple[dict, int, str]:
    """ UNCHANGED LEGACY HANDLER """
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
