"""Opt-in live probe for compose.local.yml. Reads API_KEY without printing it."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def request_json(url, payload=None, api_key=None):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=data, headers=headers)
    # The probe targets local services; ignore shell HTTP proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def local_origin(value):
    parts = urllib.parse.urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise argparse.ArgumentTypeError("use a local HTTP origin, e.g. http://127.0.0.1:5050")
    return value.rstrip("/")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify(args, api_key):
    status, _ = request_json(args.mcp_url + "/health")
    require(status == 200, "gateway health check failed")
    endpoint = args.mcp_url + "/v1/mcp/legacy"
    status, _ = request_json(endpoint, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    require(status == 401, "unauthenticated gateway access was not rejected with 401")

    request_id = 0

    def rpc(method, params=None):
        nonlocal request_id
        request_id += 1
        status, response = request_json(
            endpoint,
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
            api_key,
        )
        require(status == 200 and isinstance(response, dict), f"{method}: unexpected HTTP response")
        require(response.get("id") == request_id and "result" in response, f"{method}: invalid RPC response")
        return response["result"]

    rpc("initialize", {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "local-stack-probe", "version": "1"},
    })
    listed = rpc("tools/list")
    require(
        {t["name"] for t in listed["tools"]} == {"web_search", "fetch_url", "extract_markdown"},
        "gateway did not list the expected tools",
    )

    search_url = args.searxng_url + "/search?" + urllib.parse.urlencode({"q": args.query, "format": "json"})
    status, search = request_json(search_url)
    require(
        status == 200 and isinstance(search, dict) and isinstance(search.get("results"), list),
        "SearXNG did not return JSON search results",
    )

    def call(name, arguments):
        result = rpc("tools/call", {"name": name, "arguments": arguments})
        require(not result.get("isError"), f"{name} failed; check service logs and upstream connectivity")
        return json.loads(result["content"][0]["text"])

    search = call("web_search", {"query": args.query, "limit": 3})
    require(search.get("count", 0) > 0, "live search returned no results")
    page = call("fetch_url", {"url": "https://example.com/"})
    require(page.get("status_code") == 200 and page.get("content"), "public-page fetch was empty")
    markdown = call("extract_markdown", {"url": "https://example.com/"})
    require(markdown.get("markdown", "").strip(), "Markdown extraction was empty")
    blocked = rpc("tools/call", {"name": "fetch_url", "arguments": {"url": "http://127.0.0.1:1/"}})
    require(blocked.get("isError") is True, "loopback fetch was not rejected")
    require(
        "SSRF" in json.dumps(blocked),
        "loopback request failed without an explicit SSRF rejection",
    )
    print(json.dumps({
        "status": "ok",
        "search_results": search["count"],
        "checks": ["health", "authentication", "initialize", "tools/list", "SearXNG JSON",
                   "live search", "public fetch", "Markdown extraction", "blocked loopback"],
    }))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", type=local_origin, default="http://127.0.0.1:5050")
    parser.add_argument("--searxng-url", type=local_origin, default="http://127.0.0.1:8082")
    parser.add_argument("--query", default="Model Context Protocol")
    args = parser.parse_args()
    api_key = os.environ.get("API_KEY", "")
    if len(api_key) < 32 or any(char.isspace() for char in api_key):
        parser.error("export an API_KEY of at least 32 non-whitespace characters")
    try:
        verify(args, api_key)
    except (RuntimeError, ValueError, KeyError, TypeError, IndexError, OSError) as exc:
        # Do not print request objects, credentials, raw pages or search queries.
        message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(f"Local stack probe failed: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
