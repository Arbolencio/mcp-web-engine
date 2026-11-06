"""Offline SSRF regressions; fake DNS/transport, plus loopback-only fixtures."""

import asyncio
import socket
from types import SimpleNamespace

import pytest
from curl_cffi import CurlOpt
from fastapi import HTTPException

from mcp_web_engine import security, web_engine


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://user@example.com/",
        "http://example.com%2f@127.0.0.1/",
        "http://example.com%2f.evil/",
        "http://example.com\\@127.0.0.1/",
        " http://example.com/",
        "http://exa\nmple.com/",
        "http://example.com/\t",
        "http://example.com:bad/",
        "http://example.com:0/",
        "http://[::ffff:127.0.0.1]/",
        "http://[ff02::1]/",
        "http://[2002:7f00:1::]/",
        "http://[64:ff9b::7f00:1]/",
        "http://2130706433/",
        "http://0177.0.0.1/",
        "http://0x7f000001/",
    ],
)
def test_reject_ambiguous_or_local_urls(url):
    with pytest.raises(HTTPException):
        security.validate_ssrf_url(url)


@pytest.mark.parametrize(
    "ip",
    [
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "ff02::1",
        "100.64.0.1",
        "192.0.2.1",
        "2002:7f00:1::",
        "64:ff9b::7f00:1",
        "192.88.99.1",
        "192.0.0.9",
        "3fff::1",
        "2001:20::1",
    ],
)
def test_nonpublic_addresses(ip):
    assert security.is_ip_private(ip)


def test_url_path_is_not_unquoted():
    assert (
        security.validate_ssrf_url("https://example.com/a%2Fb?q=%40")
        == "https://example.com/a%2Fb?q=%40"
    )


def test_mixed_dns_answers_rejected(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("::ffff:127.0.0.1", 80, 0, 0),
            ),
        ],
    )
    with pytest.raises(HTTPException):
        security.validate_ssrf_url("https://example.com/")


class Transport:
    def __init__(self, monkeypatch, responses):
        self.calls = []
        self.responses = iter(responses)
        owner = self

        class Session:
            def __init__(self, **kwargs):
                self.options = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, **kwargs):
                owner.calls.append((url, self.options, kwargs))
                status, headers, chunks = next(owner.responses)
                for chunk in chunks:
                    callback = kwargs.get("content_callback")
                    if callback and callback(chunk) != len(chunk):
                        raise RuntimeError("callback aborted")
                body = b"".join(chunks)
                return SimpleNamespace(
                    status_code=status,
                    headers=headers,
                    text=body.decode(),
                    content=body,
                    encoding="utf-8",
                )

        monkeypatch.setattr(web_engine, "AsyncSession", Session)


def run(coro):
    return asyncio.run(coro)


def test_dns_is_pinned_and_environment_proxy_disabled(monkeypatch):
    dns_calls = []

    def rebinding(*args, **kwargs):
        dns_calls.append(args)
        ip = "93.184.216.34" if len(dns_calls) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    monkeypatch.setattr(security.socket, "getaddrinfo", rebinding)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    transport = Transport(monkeypatch, [(200, {}, [b"public payload content"])])
    result = run(web_engine.execute_fetch_url("https://example.com/"))
    assert result["content"] == "public payload content"
    assert len(dns_calls) == 1
    url, options, kwargs = transport.calls[0]
    assert url == "https://example.com/"  # Host and TLS SNI remain the hostname.
    assert options["trust_env"] is False
    assert options["curl_options"][CurlOpt.PROXY] == ""
    assert options["curl_options"][CurlOpt.RESOLVE] == ["example.com:443:93.184.216.34"]
    assert kwargs["allow_redirects"] is False


def test_redirect_to_localhost_is_not_fetched(monkeypatch):
    transport = Transport(monkeypatch, [(302, {"Location": "http://127.0.0.1/"}, [])])
    with pytest.raises(HTTPException):
        run(web_engine.execute_fetch_url("https://example.com/"))
    assert len(transport.calls) == 1


def test_redirect_revalidates_dns_even_for_same_hostname(monkeypatch):
    calls = []

    def dns(*a, **k):
        calls.append(a)
        ip = "93.184.216.34" if len(calls) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    monkeypatch.setattr(security.socket, "getaddrinfo", dns)
    transport = Transport(monkeypatch, [(302, {"Location": "/next"}, [])])
    with pytest.raises(HTTPException):
        run(web_engine.execute_fetch_url("https://example.com/"))
    assert len(transport.calls) == 1


def test_byte_limit_aborts_instead_of_buffering_or_slicing(monkeypatch):
    Transport(monkeypatch, [(200, {}, [b"a" * 12, b"b" * 12])])
    with pytest.raises(HTTPException) as exc:
        run(web_engine.execute_fetch_url("https://example.com/", max_bytes=16))
    assert exc.value.status_code == 413


def test_utf8_limit_counts_bytes(monkeypatch):
    Transport(monkeypatch, [(200, {}, [("é" * 12).encode()])])
    with pytest.raises(HTTPException) as exc:
        run(web_engine.execute_fetch_url("https://example.com/", max_bytes=16))
    assert exc.value.status_code == 413


def test_markdown_uses_guarded_fetch(monkeypatch):
    transport = Transport(monkeypatch, [])
    with pytest.raises(HTTPException):
        run(web_engine.execute_extract_markdown("http://[::ffff:127.0.0.1]/"))
    assert not transport.calls


def test_operator_local_search_endpoint_is_allowed(monkeypatch):
    monkeypatch.setattr(web_engine.settings, "SEARXNG_URL", "http://127.0.0.1:8888")
    transport = Transport(monkeypatch, [(200, {}, [b'{"results": []}'])])
    result = run(web_engine.execute_web_search("test"))
    assert result["results"] == []
    assert transport.calls[0][0].startswith("http://127.0.0.1:8888/search?")
    assert transport.calls[0][2]["allow_redirects"] is False


def test_real_curl_pinning_host_proxy_and_gzip_limit(monkeypatch):
    """Only our loopback fixture is contacted; policy bypass exists only in test."""
    import gzip
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("Host"))
            payload = (
                b"fixture public response" if self.path == "/ok" else b"z" * 100000
            )
            if self.path.startswith("/search"):
                payload = b'{"results": []}'
            payload = gzip.compress(payload)
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setattr(
        web_engine,
        "resolve_ssrf_target",
        lambda url: security.ValidatedTarget(
            url, "fixture.invalid", port, ("127.0.0.1",)
        ),
    )
    try:
        result = run(web_engine.execute_fetch_url(f"http://fixture.invalid:{port}/ok"))
        assert result["content"] == "fixture public response"
        assert result["content_length"] == len(b"fixture public response")
        with pytest.raises(HTTPException) as exc:
            run(
                web_engine.execute_fetch_url(
                    f"http://fixture.invalid:{port}/large", max_bytes=1024
                )
            )
        assert exc.value.status_code == 413
        monkeypatch.setattr(
            web_engine.settings, "SEARXNG_URL", f"http://127.0.0.1:{port}"
        )
        search = run(web_engine.execute_web_search("fixture test"))
        assert search["count"] == 0
        assert "error" not in search
        assert seen == [f"fixture.invalid:{port}"] * 2 + [f"127.0.0.1:{port}"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "location", [" http://127.0.0.1/", "/next\t", "http://example.com\\@127.0.0.1/"]
)
def test_raw_redirect_ambiguity_rejected(monkeypatch, location):
    transport = Transport(monkeypatch, [(302, {"Location": location}, [])])
    with pytest.raises(HTTPException):
        run(web_engine.execute_fetch_url("https://example.com/"))
    assert len(transport.calls) == 1


def test_redirect_loop_is_bounded(monkeypatch):
    transport = Transport(monkeypatch, [(302, {"Location": "/loop"}, [])] * 6)
    with pytest.raises(HTTPException) as exc:
        run(web_engine.execute_fetch_url("https://example.com/"))
    assert exc.value.detail["error"] == "TOO_MANY_REDIRECTS"
    assert len(transport.calls) == 6


def test_ddg_redirect_uses_same_ssrf_guard(monkeypatch):
    transport = Transport(monkeypatch, [(302, {"Location": "http://127.0.0.1/"}, [])])
    result = run(web_engine.execute_ddg_fallback("test"))
    assert result["results"] == []
    assert len(transport.calls) == 1


@pytest.mark.parametrize("limit", [0, -1, True, "16"])
def test_invalid_byte_limits_rejected(monkeypatch, limit):
    transport = Transport(monkeypatch, [])
    with pytest.raises(HTTPException) as exc:
        run(web_engine.execute_fetch_url("https://example.com/", max_bytes=limit))
    assert exc.value.status_code == 400
    assert not transport.calls


def test_client_cannot_raise_operator_byte_ceiling(monkeypatch):
    monkeypatch.setattr(web_engine.settings, "MAX_PAYLOAD_BYTES", 16)
    Transport(monkeypatch, [(200, {}, [b"a" * 17])])
    with pytest.raises(HTTPException) as exc:
        run(web_engine.execute_fetch_url("https://example.com/", max_bytes=100000))
    assert exc.value.status_code == 413
