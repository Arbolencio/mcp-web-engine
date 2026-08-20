# 🌐 MCP Web Engine & Search Gateway

> **Privacy-First, Self-Hostable & SSRF-Hardened MCP Server & Web Engine for AI Agents**
> **MCP Specification 2026-07-28 Pure Stateless Core & Stdio / HTTP Dual Mode**

[![PyPI Version](https://img.shields.io/badge/pypi-v1.0.5-blue.svg)](https://pypi.org/project/mcp-web-engine/)
[![npm Version](https://img.shields.io/badge/npm-v1.0.5-red.svg)](https://www.npmjs.com/package/mcp-web-engine)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚡ Instant Quickstart with `uvx` (Recommended for AI Agents)

AI agents (Claude Desktop, Cursor, Windsurf, TurboLLM, Hermes Agent) can run `mcp-web-engine` in an isolated ephemeral environment with **zero configuration**:

```bash
# Run stdio MCP server in an isolated environment (10ms startup, 0% system contamination)
uvx mcp-web-engine
```

Or run via Git repository:
```bash
uvx --from git+https://github.com/Arbolencio/mcp-web-engine mcp-web-engine
```

---

## 📌 What it does & Why it exists

`mcp-web-engine` is a high-performance Model Context Protocol (MCP) server implementing the **MCP Specification 2026-07-28 Pure Stateless Core**. It provides AI Agents with secure, private, and SSRF-hardened access to multi-engine web search, raw content fetching, and clean HTML-to-Markdown extraction.

### Key Capabilities & Architecture
- **Dual Execution Mode:**
  - **Stdio Mode (Default):** Runs JSON-RPC over `stdin`/`stdout` for direct LLM client integration (`uvx mcp-web-engine`).
  - **HTTP/SSE Server Mode:** Runs FastAPI/Uvicorn server (`mcp-web-engine --serve`).
- **Pure Stateless Core (Spec 2026-07-28):** Zero sessions, zero state, zero initialize handshake required. Every request is completely independent.
- **Protocol Methods:** Implements `server/discover`, `tools/list`, and `tools/call` with standard JSON-RPC 2.0.
- **Zero Third-Party Tracking:** Powered by an internal SearXNG meta-search engine aggregating 70+ sources with DuckDuckGo fallback.
- **Automatic URL Normalization:** Handled transparently by `normalize_searxng_url()` — any provided `SEARXNG_URL` variation (`http://127.0.0.1:8082`, `http://127.0.0.1:8082/`, `http://127.0.0.1:8082/search`) automatically appends `/search` if missing.
- **SSRF Hardened:** Pre-request DNS resolution checks prevent agents from accessing internal networks (`localhost`, `127.0.0.1`, `192.168.x.x`, `169.254.169.254`). Step-by-step HTTP 301/302 redirect re-validation.
- **Zero `--break-system-packages`:** Executed 100% in sandboxed virtual environments created on-the-fly by `uv` or `venv`.

---

## 🔌 Integration Guides

### 1. TurboLLM / Local MCP Catalog
```typescript
{
  id: 'mcp-web-engine',
  name: 'MCP Web Engine',
  cat: 'Search',
  desc: 'Privacy-first, self-hostable & SSRF-hardened web search engine and scraper for AI agents.',
  cmd: 'uvx mcp-web-engine',
  uvx: true,
  argNote: 'Requires a running SearXNG instance.',
  envs: [
    { key: 'SEARXNG_URL', desc: 'SearXNG meta-search endpoint (default: http://127.0.0.1:8082/search)', required: true },
  ],
}
```

### 2. Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "uvx",
      "args": ["mcp-web-engine"],
      "env": {
        "SEARXNG_URL": "http://127.0.0.1:8082/search"
      }
    }
  }
}
```

### 3. Cursor / Windsurf / Hermes Agent
```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "uvx",
      "args": ["mcp-web-engine"]
    }
  }
}
```

---

## 🛠️ Provided MCP Tools

| Tool Name | Parameters | Description |
|---|---|---|
| `web_search` | `query` (str), `limit` (int, default: 10) | Multi-engine meta-search via SearXNG returning structured JSON results |
| `fetch_url` | `url` (str), `max_bytes` (int, optional) | Fetches raw web content after strict SSRF security validation |
| `extract_markdown` | `url` (str), `max_bytes` (int, optional) | Scrapes a webpage and converts HTML into clean, LLM-optimized Markdown |

---

## ⚙️ Configuration & Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SEARXNG_URL` | **Yes** | `http://127.0.0.1:8082/search` | SearXNG meta-search endpoint (Auto-normalizes trailing slashes and missing `/search`) |
| `PORT` | No | `5050` | HTTP/SSE server port (Used only when running in `--serve` mode) |
| `HOST` | No | `0.0.0.0` | HTTP/SSE server binding host |
| `API_KEY` | No | `""` | Optional authentication key for HTTP endpoints |

---

## 🛠️ Development & Building

```bash
# Clone Repository
git clone https://github.com/Arbolencio/mcp-web-engine.git
cd mcp-web-engine

# Build Wheel for PyPI
python3 -m build --wheel

# Run locally in stdio mode via uv
uv run python -m mcp_web_engine.main

# Run locally in HTTP server mode via uv
uv run python -m mcp_web_engine.main --serve
```

---

## 🛡️ Security & Environment Isolation

- **SSRF Hardening:** Blocks `localhost`, loopbacks, private subnets (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), percent-encoding bypasses (`%31%32%37...`), and re-validates `Location` headers on HTTP redirects step-by-step.
- **Zero Package Pollution:** Execution via `uvx` or `bin/cli.js` never modifies global site-packages or uses dangerous flags like `--break-system-packages`.

---

## 📄 License

MIT License © 2026 MCP Web Engine Contributors.
