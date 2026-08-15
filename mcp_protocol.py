"""
MCP Protocol 2026-07-28 Streamable HTTP / JSON-RPC 2.0 Handler Module
Implements standard JSON-RPC 2.0 message handling for tools/list, tools/call, and initialize.
"""
import json
import time
from fastapi import Response, status
from mcp_tools import MCP_TOOL_DEFINITIONS, handle_mcp_tool_call
from logging_obs import logger, metrics

MCP_PROTOCOL_VERSION = "2026-07-28"

# Standard JSON-RPC 2.0 Error Codes
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

async def process_mcp_jsonrpc_request(payload: dict) -> tuple[dict, int]:
    """
    Processes an incoming JSON-RPC 2.0 MCP request according to specification 2026-07-28.
    Returns (response_dict, http_status_code).
    """
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return make_jsonrpc_error(payload.get("id"), INVALID_REQUEST, "Invalid JSON-RPC 2.0 request."), status.HTTP_400_BAD_REQUEST

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {})

    # 1. initialize Handshake (Stateless compatible)
    if method == "initialize":
        res_data = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False}
            },
            "serverInfo": {
                "name": "mcp-web-engine",
                "version": "1.0.0"
            }
        }
        return make_jsonrpc_response(request_id, res_data), status.HTTP_200_OK

    # 2. notifications/initialized (Stateless notification)
    elif method == "notifications/initialized":
        return {}, status.HTTP_202_ACCEPTED

    # 3. tools/list Discovery
    elif method == "tools/list":
        res_data = {
            "tools": MCP_TOOL_DEFINITIONS
        }
        return make_jsonrpc_response(request_id, res_data), status.HTTP_200_OK

    # 4. tools/call Execution
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

            # Format result according to MCP Content Standard
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

            # Standard MCP Tool Error Output
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

    # 5. Method Not Found
    else:
        return make_jsonrpc_error(request_id, METHOD_NOT_FOUND, f"Method '{method}' not found or unsupported."), status.HTTP_404_NOT_FOUND
