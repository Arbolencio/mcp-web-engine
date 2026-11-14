# Local stack with SearXNG included

`compose.local.yml` starts MCP Web Engine in HTTP mode and an operator-controlled
SearXNG instance with JSON search enabled. It is independent of `docker-compose.yml`,
which continues to use an existing search backend. Use the standalone file, not
both files together. Requires Docker with Compose v2 supporting `up --wait`.

From the repository root, generate two separate secrets in a POSIX shell:

```bash
export API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SEARXNG_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose -f compose.local.yml up --build -d --wait
```

Python 3 is used here only to generate secrets; the server runs inside Docker.
In PowerShell, the first two commands are instead:

```powershell
$env:API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:SEARXNG_SECRET = python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep both values in your local secret manager or a private environment file for
later starts. Do not generate a new API key on every restart: changing the key
changes the identity used for admission accounting. Compose reads `.env` for
interpolation; the Python application does not load it automatically. Never
commit secrets.

The default host endpoints are:

| Service | URL | Authentication |
|---|---|---|
| SearXNG | `http://127.0.0.1:8082` | Local access; no API key |
| MCP Web Engine | `http://127.0.0.1:5050` | Bearer `API_KEY` on protected routes |

Both ports bind to host loopback. Internally the gateway uses
`http://searxng:8080/search`; a host `SEARXNG_URL` variable does not override that
connection. If either host port is occupied, set `LOCAL_SEARXNG_PORT` or
`LOCAL_MCP_PORT` before starting. The containers' ports stay unchanged.

## Verify the setup

```bash
python3 examples/verify_local_stack.py
```

The opt-in probe uses `API_KEY` from the environment and performs a real search,
fetches `https://example.com/`, extracts Markdown and checks that a public-fetch
request to loopback is rejected. It also verifies JSON search is enabled and that
protected gateway routes reject an unauthenticated request. It never prints the
key. For alternate ports, pass `--mcp-url` and `--searxng-url`; use `--help`.
This probe accesses public search engines and example.com and is not run by the
offline test suite. Upstream timeouts, CAPTCHAs, network restrictions or empty
results can fail the live probe even when the containers are healthy.

The health checks test service liveness; `up --wait` does not establish search
quality or upstream connectivity. Inspect failures with:

```bash
docker compose -f compose.local.yml ps
docker compose -f compose.local.yml logs --tail=100
```

## Connect a local MCP client

For Claude Desktop, Cursor or another local stdio client, use the existing README
stdio configuration with `SEARXNG_URL=http://127.0.0.1:8082/search` (or your selected
host port) and `ALLOW_DDG_FALLBACK=false`. The client launches its own stdio server;
it uses SearXNG from this stack and does not need the HTTP API key. Host `uvx`/npm
prerequisites still apply to that client process.

The containerized gateway provides the documented HTTP routes. Its stateless route
is a project extension, and SSE support is limited; validate the transport needs
of a remote client before connecting it.

## State, configuration and upgrades

This stack has its own Compose project name and volumes, separate from the
existing Compose setup. `local-usage-state` preserves HTTP accounting and
`searxng-data` preserves SearXNG cache data. Keep both volumes during upgrades.
Use `docker compose -f compose.local.yml stop` to stop the stack. Never use
`down -v` as routine cleanup: it deletes the stack's stored data.

SearXNG is pinned to a reviewed image digest. To upgrade it, review a new official
image, update the digest in `compose.local.yml`, and rerun the live probe. Its
settings live in `searxng/settings.yml`; restart SearXNG after changing them.
The three-second engine deadline fits the gateway's four-second search timeout,
but slow engines may return fewer results. The loopback-only setup disables the
SearXNG bot limiter and does not need Valkey. These defaults are for a local
instance, not a public SearXNG deployment.

Search queries leave the host through SearXNG and its upstream engines. Direct
DuckDuckGo fallback stays disabled. Public pages are untrusted input. See
[operating boundaries](operations.md) for HTTP authentication, storage and egress
limitations.
