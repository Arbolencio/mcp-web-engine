"""Record a real stdio MCP session; no model account or graphical client required.

Usage: python examples/demo.py --output docs/assets/demo-session.json
Requires uv on PATH, Python >=3.11 and a JSON-enabled SearXNG backend.
This makes one real search and two requests to example.com. No fixture responses.
"""
import argparse
import datetime
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def requests():
    return [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'recorded-demo', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'web_search', 'arguments': {'query': 'Model Context Protocol documentation', 'limit': 3}}},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'fetch_url', 'arguments': {'url': 'https://example.com/'}}},
        {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'extract_markdown', 'arguments': {'url': 'https://example.com/'}}},
    ]


def validate(responses):
    if [r.get('id') for r in responses] != [1, 2, 3, 4, 5]:
        raise ValueError('Expected five ordered responses and a silent notification')
    for response in responses:
        if response.get('error') or response.get('result', {}).get('isError'):
            raise ValueError('Live tool failed; refusing to record a success demo')
    tools = {t['name'] for t in responses[1]['result']['tools']}
    if tools != {'web_search', 'fetch_url', 'extract_markdown'}:
        raise ValueError('Unexpected tool list')
    search = json.loads(responses[2]['result']['content'][0]['text'])
    if search.get('error') or not search.get('results'):
        raise ValueError('Search returned no usable live results')


def record():
    command = ['uvx', '--default-index', 'https://pypi.org/simple', 'mcp-web-engine==1.2.1']
    env = os.environ.copy()
    for key in ('API_KEY', 'MCP_WEB_ENGINE_ENV_FILE', 'PYTHONPATH'):
        env.pop(key, None)
    env['ALLOW_DDG_FALLBACK'] = 'false'
    env.setdefault('SEARXNG_URL', 'http://127.0.0.1:8082/search')
    with tempfile.TemporaryDirectory(prefix='mcp-real-demo-', dir=os.environ.get('TMPDIR')) as folder:
        env['MCP_WEB_ENGINE_STATE_DB'] = str(Path(folder) / 'usage.sqlite3')
        env['MCP_WEB_ENGINE_BETA_KEYS_FILE'] = str(Path(folder) / 'keys.json')
        started = time.monotonic()
        process = subprocess.run(command, input=''.join(json.dumps(r) + '\n' for r in requests()), text=True, capture_output=True, cwd=folder, env=env, timeout=90)
        if process.returncode:
            raise RuntimeError('Server failed; check uv, Python and backend configuration')
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        validate(responses)
        return {'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'command': command, 'transport': 'stdio', 'source': 'live network execution; not mocked', 'elapsed_seconds': round(time.monotonic() - started, 3), 'requests': requests(), 'responses': responses}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = record()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n')
    print(json.dumps({'recorded': str(args.output), 'responses': len(data['responses']), 'elapsed_seconds': data['elapsed_seconds']}))
