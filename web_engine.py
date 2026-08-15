"""
Core Web Engine Module: SearXNG Connector, SSRF-Safe HTTP Fetcher with Redirect Validation & HTML/Markdown Parser
"""
import time
import urllib.parse
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

async def execute_web_search(query: str, limit: int = 10):
    start_t = time.time()
    url = f"{settings.SEARXNG_URL}?q={query}&format=json"
    
    async with AsyncSession() as session:
        try:
            r = await session.get(url, timeout=settings.DEFAULT_TIMEOUT_SEC)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": "BACKEND_ERROR", "message": f"SearXNG service error: {str(e)}"}
            )

    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "SEARCH_FAILED", "message": f"SearXNG returned HTTP status {r.status_code}."}
        )

    try:
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "PARSE_ERROR", "message": f"Failed to parse search response: {str(e)}"}
        )

async def execute_fetch_url(url: str, max_bytes: int = None):
    """
    Fetches raw text content with manual redirect handling and strict SSRF re-validation per hop.
    """
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

            # Check Redirect (301, 302, 303, 307, 308)
            if r.status_code in [301, 302, 303, 307, 308]:
                location = r.headers.get("Location") or r.headers.get("location")
                if not location:
                    break
                
                # Resolve relative redirect URL
                next_url = urllib.parse.urljoin(current_url, location)
                # Re-validate destination URL against SSRF
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
