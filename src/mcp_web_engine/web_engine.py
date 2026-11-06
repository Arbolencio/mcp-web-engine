"""
Core Web Engine Module: SearXNG Connector with DuckDuckGo Direct Fallback, SSRF-Safe HTTP Fetcher & HTML/Markdown Parser
"""

import asyncio
import json
import logging
import re
import time
import urllib.parse

import html2text
from bs4 import BeautifulSoup
from curl_cffi import CurlError, CurlOpt
from curl_cffi.curl import CURL_WRITEFUNC_ERROR
from curl_cffi.requests import AsyncSession
from fastapi import HTTPException, status

from .config import settings
from .security import _parse_http_url, resolve_ssrf_target

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def get_headers():
    return {
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="120"',
        "Sec-Fetch-Dest": "document",
    }


async def execute_ddg_fallback(query: str, limit: int = 10):
    """
    Direct DuckDuckGo HTML Search Fallback if SearXNG is unavailable.
    """
    start_t = time.time()
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        r, body, _ = await _bounded_request(ddg_url, _payload_limit(), timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(_decode_body(r, body), "html.parser")
            results = []
            for idx, a in enumerate(soup.find_all("a", class_="result__a")[:limit]):
                title = a.get_text(strip=True)
                raw_href = a.get("href", "")
                # Extract target URL from DDG redirect
                match = re.search(r"uddg=(https?%3A%2F%2F[^&]+)", raw_href)
                final_url = urllib.parse.unquote(match.group(1)) if match else raw_href
                results.append(
                    {
                        "rank": idx + 1,
                        "title": title,
                        "url": final_url,
                        "snippet": f"Search result for '{query}'",
                        "engine": "duckduckgo_fallback",
                    }
                )
            return {
                "query": query,
                "count": len(results),
                "latency_ms": round((time.time() - start_t) * 1000, 2),
                "results": results,
            }
    except (HTTPException, ValueError, TypeError, AttributeError) as exc:
        logger.warning("DuckDuckGo fallback unavailable (%s)", type(exc).__name__)

    return {"query": query, "count": 0, "latency_ms": 0, "results": []}


def normalize_searxng_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if not url.endswith("/search"):
        url = f"{url}/search"
    return url


async def execute_web_search(query: str, limit: int = 10):
    start_t = time.time()
    base_searxng = normalize_searxng_url(settings.SEARXNG_URL)
    query_params = urllib.parse.urlencode({"q": query, "format": "json"})
    url = f"{base_searxng}?{query_params}"

    try:
        r, body, _ = await _bounded_request(
            url, _payload_limit(), trusted_search=True, timeout=4.0
        )
        if r.status_code == 200:
            data = json.loads(_decode_body(r, body))
            results = data.get("results", [])[:limit]
            items = []
            for idx, item in enumerate(results):
                items.append(
                    {
                        "rank": idx + 1,
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "snippet": item.get("content"),
                        "engine": item.get("engine"),
                    }
                )
            return {
                "query": query,
                "count": len(items),
                "latency_ms": round((time.time() - start_t) * 1000, 2),
                "results": items,
            }
    except (HTTPException, ValueError, TypeError, AttributeError) as exc:
        logger.warning("SearXNG unavailable (%s)", type(exc).__name__)

    # SearXNG failed or timed out -> only fall back when the operator opted in,
    # so that no query ever leaves the host without explicit consent.
    if settings.ALLOW_DDG_FALLBACK:
        return await execute_ddg_fallback(query, limit)

    return {
        "query": query,
        "count": 0,
        "latency_ms": round((time.time() - start_t) * 1000, 2),
        "results": [],
        "error": "SEARXNG_UNAVAILABLE",
        "detail": "SearXNG did not answer. The DuckDuckGo fallback is disabled by default; set ALLOW_DDG_FALLBACK=true to enable it.",
    }


def _payload_limit(max_bytes=None):
    ceiling = settings.MAX_PAYLOAD_BYTES
    if max_bytes is None:
        return ceiling
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise HTTPException(
            400,
            detail={"error": "INVALID_LIMIT", "message": "max_bytes must be positive."},
        )
    return min(max_bytes, ceiling)


async def _bounded_request(url, byte_limit, *, trusted_search=False, timeout=None):
    """Private transport. Only the configured operator search URL may bypass SSRF.

    Each hop gets a fresh session/connection: no stale DNS cache, pooled HTTP/2
    coalescing, cross-origin cookies, or environment proxies. curl's write callback
    receives decompressed data and aborts before retaining more than byte_limit.
    """
    deadline = time.monotonic() + (timeout or settings.DEFAULT_TIMEOUT_SEC)
    current_url = url
    for redirect_count in range(6):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(504, detail={"error": "FETCH_TIMEOUT"})
        if trusted_search:
            current_url, _, _ = _parse_http_url(current_url)
            target = None
        else:
            # Offload blocking resolver; outer wait bounds the caller's DNS wait.
            try:
                target = await asyncio.wait_for(
                    asyncio.to_thread(resolve_ssrf_target, current_url), remaining
                )
            except asyncio.TimeoutError:
                raise HTTPException(504, detail={"error": "FETCH_TIMEOUT"}) from None
            current_url = target.url
        options = {
            # Set the exact canonical URL last, after requests library requoting.
            CurlOpt.URL: current_url,
            CurlOpt.PROXY: "",  # trust_env alone is insufficient in older releases.
            CurlOpt.NOPROXY: "*",
            CurlOpt.PROTOCOLS: 3,  # CURLPROTO_HTTP | CURLPROTO_HTTPS
            CurlOpt.REDIR_PROTOCOLS: 3,
            CurlOpt.FRESH_CONNECT: 1,
            CurlOpt.FORBID_REUSE: 1,
        }
        if target is not None:
            options[CurlOpt.RESOLVE] = [target.resolve_entry]
        body = bytearray()
        oversized = False

        def receive(chunk, body=body):
            nonlocal oversized
            if len(body) + len(chunk) > byte_limit:
                oversized = True
                # Older curl_cffi ignores a short byte count: use the explicit
                # libcurl abort sentinel instead of 0 (verified on 0.6 and 0.17).
                return CURL_WRITEFUNC_ERROR
            body.extend(chunk)
            return len(chunk)

        try:
            async with AsyncSession(trust_env=False, curl_options=options) as session:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                r = await asyncio.wait_for(
                    session.get(
                        current_url,
                        headers=get_headers(),
                        impersonate="chrome120",
                        allow_redirects=False,
                        timeout=remaining,
                        content_callback=receive,
                        accept_encoding="gzip, deflate, br",
                    ),
                    remaining,
                )
        except (CurlError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
            if oversized:
                raise HTTPException(
                    413,
                    detail={
                        "error": "PAYLOAD_TOO_LARGE",
                        "message": "Decoded response exceeds byte limit.",
                    },
                ) from None
            timed_out = (
                isinstance(exc, asyncio.TimeoutError) or "timeout" in str(exc).lower()
            )
            # Never echo transport exceptions (may include sensitive URL data).
            raise HTTPException(
                504 if timed_out else 502,
                detail={"error": "FETCH_ERROR", "message": "Target request failed."},
            ) from None
        if oversized:
            raise HTTPException(413, detail={"error": "PAYLOAD_TOO_LARGE"})
        if r.status_code not in (301, 302, 303, 307, 308) or trusted_search:
            return r, bytes(body), current_url
        location = r.headers.get("Location") or r.headers.get("location")
        if not location:
            return r, bytes(body), current_url
        if redirect_count == 5:
            raise HTTPException(502, detail={"error": "TOO_MANY_REDIRECTS"})
        # Validate raw Location BEFORE urljoin, which also strips some controls.
        if (
            not isinstance(location, str)
            or "\\" in location
            or any(ord(c) <= 32 or ord(c) == 127 or c.isspace() for c in location)
        ):
            raise HTTPException(400, detail={"error": "INVALID_REDIRECT"})
        current_url = urllib.parse.urljoin(current_url, location)
    raise HTTPException(502, detail={"error": "TOO_MANY_REDIRECTS"})


def _decode_body(response, body):
    try:
        return body.decode(response.encoding or "utf-8", errors="replace")
    except (LookupError, AttributeError):
        return body.decode("utf-8", errors="replace")


async def execute_fetch_url(url: str, max_bytes: int | None = None):
    start_t = time.monotonic()
    r, body, current_url = await _bounded_request(url, _payload_limit(max_bytes))
    if r.status_code != 200:
        raise HTTPException(
            502,
            detail={
                "error": "HTTP_FETCH_FAILED",
                "message": f"Target server returned HTTP status {r.status_code}.",
            },
        )
    content = _decode_body(r, body)
    if not content or len(content.strip()) < 10:
        raise HTTPException(
            422,
            detail={
                "error": "EMPTY_RESPONSE",
                "message": "Target returned an empty payload.",
            },
        )
    return {
        "url": current_url,
        "status_code": r.status_code,
        "content_length": len(body),
        "latency_ms": round((time.monotonic() - start_t) * 1000, 2),
        "content": content,
    }


async def execute_extract_markdown(url: str, max_bytes: int | None = None):
    fetch_res = await execute_fetch_url(url, max_bytes)
    html_content = fetch_res["content"]

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "iframe"]):
            tag.decompose()

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0

        markdown_text = h.handle(str(soup))

        return {
            "url": fetch_res["url"],
            "status_code": 200,
            "markdown_length": len(markdown_text),
            "latency_ms": fetch_res["latency_ms"],
            "markdown": markdown_text,
        }
    except (ValueError, TypeError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "EXTRACTION_FAILED",
                "message": "Failed to convert HTML to Markdown.",
            },
        )
