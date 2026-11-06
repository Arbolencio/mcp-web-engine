# MCP Web Engine

Self-hostable MCP search, public-page fetch and Markdown extraction. Source version: **1.2.0**; examples below run the checkout, not an assumed published release.

Requires Python >=3.11. The optional npm launcher requires Node >=18 and [uv](https://docs.astral.sh/uv/getting-started/installation/) on PATH. Installation resolves dependencies from `pyproject.toml` and may access package indexes. uv isolates Python dependencies; it is not a security sandbox.

## Local stdio

```bash
git clone https://github.com/Arbolencio/mcp-web-engine.git
cd mcp-web-engine
uv run mcp-web-engine
```

Default transport is newline-delimited JSON-RPC over stdin/stdout. Diagnostics and installer output belong on stderr. Clients should initialize, send `notifications/initialized`, then use `ping`, `tools/list`, and `tools/call`. No search service is required for initialization or listing tools.

Client configuration (replace the absolute checkout path):

```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "uv",
      "args": ["tool", "run", "--from", "/absolute/path/mcp-web-engine", "mcp-web-engine"],
      "env": {"SEARXNG_URL": "http://127.0.0.1:8082/search", "ALLOW_DDG_FALLBACK": "false"}
    }
  }
}
```

The npm tarball includes the canonical Python src package and build metadata. `npx --package /absolute/path/mcp-web-engine-1.2.0.tgz mcp-web-engine` delegates to uv; Python/uv remain prerequisites, and first launch may need network access for dependencies.

## HTTP

```bash
export API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SEARXNG_URL=http://127.0.0.1:8082/search
uv run mcp-web-engine --serve
```

HTTP defaults to `127.0.0.1:5050`; `API_KEY` must contain at least 32 non-whitespace characters. Send `Authorization: Bearer <your-key>` to protected endpoints. Keep the key out of source control and URLs. `/health` is a liveness endpoint, not a SearXNG connectivity check.

`POST /v1/mcp/legacy` provides the initialize-based compatibility path. `/v1/mcp` is a project-specific stateless extension requiring `Mcp-Method` (and `Mcp-Name` for tool calls). Its `2026-07-28` label is an internal extension identifier, **not a claim of official MCP conformance**. SSE support is limited; this is not a complete implementation of every MCP transport or optional feature.

## Tools

| Tool | Arguments | Purpose |
|---|---|---|
| `web_search` | `query`, optional `limit` | Search through configured SearXNG |
| `fetch_url` | `url`, optional `max_bytes` | Fetch a public HTTP(S) page |
| `extract_markdown` | `url`, optional `max_bytes` | Convert fetched HTML to Markdown |

Use `tools/list` for authoritative schemas and bounds.

## Configuration

Process environment is authoritative. CWD `.env` files are **not** loaded automatically. To explicitly load one, set `MCP_WEB_ENGINE_ENV_FILE` to an existing **absolute** file path; process variables override file values.

| Variable | Default | Meaning |
|---|---|---|
| `SEARXNG_URL` | `http://127.0.0.1:8082/search` | Trusted operator-controlled search backend; search needs it running |
| `ALLOW_DDG_FALLBACK` | `false` | Opt in to sending queries to DuckDuckGo if SearXNG fails |
| `API_KEY` | empty | Operator-generated HTTP bearer key; mandatory for CLI HTTP mode |
| `HOST` / `PORT` | `127.0.0.1` / `5050` | HTTP bind address and port |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-key HTTP admission limit, persisted in local SQLite |
| `DEFAULT_TIMEOUT_SEC` | `10` | Outbound timeout, up to 120 seconds |
| `MAX_PAYLOAD_BYTES` | `2097152` | Payload ceiling, up to 16 MiB |
| `MCP_WEB_ENGINE_STATE_DB` | `$XDG_STATE_HOME/mcp-web-engine/usage.sqlite3` (or `~/.local/state/...`) | Local SQLite admission quotas and per-key tool telemetry; share one local file across workers |
| `MCP_WEB_ENGINE_BETA_KEYS_FILE` | Same state directory, `beta_keys.json` | Operator-managed credentials, separate from telemetry; use an absolute path |
| `LOG_LEVEL` / `ENV` | `INFO` / `production` | Logging and environment settings |

## Docker

```bash
# With API_KEY already exported as above:
docker compose up --build -d
```

The image installs the Python package, runs as a non-root user and explicitly starts `mcp-web-engine --serve` on port 5050. Compose publishes **only host loopback**. Container `HOST=0.0.0.0` is necessary for that port mapping; do not confuse it with the host binding. Set `SEARXNG_URL` to a reachable backend: compose defaults to `http://host.docker.internal:8082/search`, using the host gateway. An instance bound only to host loopback may not be reachable from Docker. No SearXNG instance or credentials are bundled. See [operations and limitations](docs/operations.md).

## Security controls and limitations

Public fetches validate schemes, resolved addresses and redirects, rejecting loopback/private/reserved destinations. Bounded payloads, timeouts and tool argument validation reduce resource exposure. These are defense-in-depth controls, not a guarantee against all SSRF, DNS, routing, proxy or upstream failures; enforce outbound network policy independently.

SearXNG is an intentional trusted-backend exception to public-fetch restrictions and can use a private address. Its operator and upstream engines receive queries; self-hosting does not keep searches entirely on-host. DuckDuckGo fallback is off by default, but ordinary SearXNG searches still involve upstream services. Fetched pages are untrusted input and may contain prompt injection. Dependency isolation does not isolate filesystem/network access. HTTP authentication is not TLS or a multi-host distributed rate limiter; use a restricted network and a TLS reverse proxy when needed. Do not expose the service directly to the Internet.

## Development and artifact verification

```bash
uv sync --extra test
uv run pytest -q
uv run --with build python -m build
npm pack
python3 tests/artifact_smoke.py -- uv tool run --from /absolute/path/to/package.whl mcp-web-engine
```

Tests are offline by default. The artifact smoke sends no search query: initialize, silent notification, ping, tool listing, and a rejected loopback fetch. CI tests Python 3.11–3.13 and builds/installs wheel and npm artifacts outside the checkout. Package dependency installation still requires package-index access unless cached.

MIT License. See [LICENSE](LICENSE).
