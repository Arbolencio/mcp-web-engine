"""
Core Web Engine Module: SearXNG Connector with DuckDuckGo Direct Fallback, SSRF-Safe HTTP Fetcher & HTML/Markdown Parser
"""
import time
import urllib.parse
import re
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import html2text
from fastapi import HTTPException, status
from config import settings
from security import validate_ssrf_url

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def get_headers():
    return {
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="120"',
        "Sec-Fetch-Dest": "document"
    }

async def execute_ddg_fallback(query: str, limit: int = 10):
    """
    Direct DuckDuckGo HTML Search Fallback if SearXNG is unavailable.
    """
    start_t = time.time()
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = get_headers()

    async with AsyncSession() as session:
        try:
            r = await session.get(ddg_url, headers=headers, impersonate="chrome120", timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                results = []
                for idx, a in enumerate(soup.find_all("a", class_="result__a")[:limit]):
                    title = a.get_text(strip=True)
                    raw_href = a.get("href", "")
                    # Extract target URL from DDG redirect
                    match = re.search(r"uddg=(https?%3A%2F%2F[^&]+)", raw_href)
                    final_url = urllib.parse.unquote(match.group(1)) if match else raw_href
                    results.append({
                        "rank": idx + 1,
                        "title": title,
                        "url": final_url,
                        "snippet": f"Search result for '{query}'",
                        "engine": "duckduckgo_fallback"
                    })
                return {
                    "query": query,
                    "count": len(results),
                    "latency_ms": round((time.time() - start_t) * 1000, 2),
                    "results": results
                }
        except Exception:
            pass

    return {"query": query, "count": 0, "latency_ms": 0, "results": []}

async def execute_web_search(query: str, limit: int = 10):
    start_t = time.time()
    url = f"{settings.SEARXNG_URL}?q={query}&format=json"
    
    async with AsyncSession() as session:
        try:
            r = await session.get(url, timeout=4.0)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])[:limit]
                items = []
                for idx, item in enumerate(results):
                    items.append({
                        "rank": idx + 1,
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "snippet": item.get("content"),
                        "engine": item.get("engine")
                    })
                return {
                    "query": query,
                    "count": len(items),
                    "latency_ms": round((time.time() - start_t) * 1000, 2),
                    "results": items
                }
        except Exception:
            pass

    # SearXNG failed or timed out -> Fallback to direct DuckDuckGo HTML parser
    return await execute_ddg_fallback(query, limit)

async def execute_fetch_url(url: str, max_bytes: int = None):
    current_url = validate_ssrf_url(url)
    byte_limit = max_bytes or settings.MAX_PAYLOAD_BYTES

    start_t = time.time()
    headers = get_headers()
    max_redirects = 5
    redirect_count = 0

    async with AsyncSession() as session:
        while redirect_count < max_redirects:
            try:
                r = await session.get(
                    current_url,
                    headers=headers,
                    impersonate="chrome120",
                    allow_redirects=False,
                    timeout=settings.DEFAULT_TIMEOUT_SEC
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT if "timeout" in str(e).lower() else status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "FETCH_ERROR", "message": f"Failed to fetch target URL: {str(e)}"}
                )

            if r.status_code in [301, 302, 303, 307, 308]:
                location = r.headers.get("Location") or r.headers.get("location")
                if not location:
                    break
                next_url = urllib.parse.urljoin(current_url, location)
                current_url = validate_ssrf_url(next_url)
                redirect_count += 1
                continue
            else:
                break

    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "HTTP_FETCH_FAILED", "message": f"Target server returned HTTP status {r.status_code}."}
        )

    content = r.text[:byte_limit]
    if not content or len(content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "EMPTY_RESPONSE", "message": "Target URL returned an empty or truncated payload."}
        )

    return {
        "url": current_url,
        "status_code": r.status_code,
        "content_length": len(content),
        "latency_ms": round((time.time() - start_t) * 1000, 2),
        "content": content
    }

async def execute_extract_markdown(url: str, max_bytes: int = None):
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
            "markdown": markdown_text
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "EXTRACTION_FAILED", "message": f"Failed to convert HTML to Markdown: {str(e)}"}
        )
