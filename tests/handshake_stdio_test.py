#!/usr/bin/env python3
"""Offline installed-entrypoint smoke; safe to import during pytest collection."""
import json
import os
import subprocess
import sys

MESSAGES = [
    {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'TurboLLM', 'version': 'smoke'}}},
    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
    {'jsonrpc': '2.0', 'id': 3, 'method': 'ping'},
    {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'fetch_url', 'arguments': {'url': 'http://127.0.0.1/private'}}},
]


def smoke(command=None):
    command = command or [sys.executable, '-m', 'mcp_web_engine.main']
    env = {k: v for k, v in os.environ.items() if k != 'MCP_WEB_ENGINE_ENV_FILE'}
    env['ALLOW_DDG_FALLBACK'] = 'false'
    result = subprocess.run(command, input=''.join(json.dumps(m) + '\n' for m in MESSAGES), capture_output=True, text=True, timeout=60, env=env)
    assert result.returncode == 0, result.stderr
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert [r['id'] for r in replies] == [1, 2, 3, 4], result.stdout
    assert replies[0]['result']['protocolVersion'] == '2024-11-05'
    assert replies[0]['result']['serverInfo']['version'] == '1.2.0'
    assert {t['name'] for t in replies[1]['result']['tools']} == {'web_search', 'fetch_url', 'extract_markdown'}
    assert replies[2]['result'] == {}
    assert replies[3]['result']['isError'] is True
    return {'entrypoint': command, 'responses': len(replies), 'notification_silent': True, 'private_fetch_blocked': True}


def test_stdio_handshake():
    smoke()


if __name__ == '__main__':
    print(json.dumps(smoke(sys.argv[1:] or None), indent=2))
