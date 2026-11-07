"""Offline content decoding and markdown safety regressions."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from mcp_web_engine import web_engine as engine
from mcp_web_engine.mcp_tools import ExtractMarkdownInput, FetchUrlInput


@pytest.mark.parametrize('model', [FetchUrlInput, ExtractMarkdownInput])
@pytest.mark.parametrize('value', [True, '1024', 10.0])
def test_mcp_byte_limit_rejects_type_coercion(model, value):
    with pytest.raises(ValidationError):
        model(url='https://example.com/', max_bytes=value)


@pytest.mark.parametrize('content_type', ['application/pdf', 'image/png', 'application/octet-stream', 'video/mp4'])
@pytest.mark.asyncio
async def test_binary_content_type_rejected(monkeypatch, content_type):
    async def request(url, *args, **kwargs):
        return SimpleNamespace(status_code=200, encoding='utf-8', headers={'Content-Type': content_type}), b'not a text document', url
    monkeypatch.setattr(engine, '_bounded_request', request)
    with pytest.raises(HTTPException) as exc:
        await engine.execute_fetch_url('https://example.com/')
    assert exc.value.status_code == 415


@pytest.mark.parametrize('encoding', ['unknown-charset', 'base64_codec', 'rot_13'])
def test_untrusted_charset_falls_back(encoding):
    assert engine._decode_body(SimpleNamespace(encoding=encoding), b'plain text payload') == 'plain text payload'


@pytest.mark.asyncio
async def test_markdown_removes_dangerous_links_and_resolves_relative(monkeypatch):
    async def fetch(*args):
        return {'url': 'https://example.com/base/page', 'latency_ms': 0, 'content': '''<p>Article content here</p>
        <a href="javascript:alert(1)">Javascript</a><a href="data:text/html,evil">Data</a>
        <a href="file:///etc/passwd">File</a><a href="/safe">Safe</a>
        <a href="https://example.org/">External</a>'''}
    monkeypatch.setattr(engine, 'execute_fetch_url', fetch)
    result = await engine.execute_extract_markdown('https://example.com/')
    assert 'javascript:' not in result['markdown']
    assert 'data:' not in result['markdown']
    assert 'file:' not in result['markdown']
    assert '(https://example.com/safe)' in result['markdown']
    assert '(https://example.org/)' in result['markdown']


@pytest.mark.parametrize('content_type', ['text/html; charset=utf-8', 'text/plain', 'application/json', 'application/problem+json', 'application/xhtml+xml', ''])
@pytest.mark.asyncio
async def test_supported_text_content_types(monkeypatch, content_type):
    async def request(url, *args, **kwargs):
        return SimpleNamespace(status_code=200, encoding='utf-8', headers={'Content-Type': content_type}), b'supported text document', url
    monkeypatch.setattr(engine, '_bounded_request', request)
    assert (await engine.execute_fetch_url('https://example.com/'))['content'] == 'supported text document'


def test_real_curl_rejects_excessive_response_headers(monkeypatch):
    """Exercise the actual bundled libcurl header ceiling, not a fictitious option."""
    import asyncio
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from mcp_web_engine.security import ValidatedTarget

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('X-Oversized', 'x' * (400 * 1024))
            self.end_headers()
            try:
                self.wfile.write(b'fixture content')
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.setattr(engine, 'resolve_ssrf_target', lambda url: ValidatedTarget(url, 'fixture.invalid', port, ('127.0.0.1',)))
    try:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(engine.execute_fetch_url(f'http://fixture.invalid:{port}/'))
        assert exc.value.status_code == 502
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
