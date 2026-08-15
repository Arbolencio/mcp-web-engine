# 🌐 MCP Web Engine & Search Gateway

> **Official Specification 2026-07-28 Streamable HTTP / JSON-RPC 2.0 MCP Server & Web Engine for AI Agents**

---

## 📌 What it does & Why it exists

`MCP Web Engine` is a lightweight, high-performance Model Context Protocol (MCP) server conforming to the **MCP Specification 2026-07-28 (Streamable HTTP / JSON-RPC 2.0 core)**. It gives AI Agents (Claude Desktop, Cursor, Windsurf, Inspector, Hermes Agent) secure, private access to web search, raw content fetching, and clean HTML-to-Markdown extraction.

### Why build this?
- **Official Spec 2026-07-28 Compliant:** Uses standard JSON-RPC 2.0 over Streamable HTTP (`/v1/mcp`) supporting `initialize`, `tools/list`, and `tools/call`.
- **Zero Third-Party Tracking:** Uses internal SearXNG meta-search engine aggregating 70+ sources with DuckDuckGo fallback.
- **SSRF Hardened:** Pre-request DNS resolution checks prevent agents from accessing internal networks (`localhost`, `127.0.0.1`, `192.168.x.x`, `169.254.169.254`).
- **TLS Fingerprinting:** Powered by `curl_cffi` (Chrome 120+ TLS impersonation) for clean research scraping without heavy browser overhead.

---

## 🏗️ Architecture

```
[ MCP Client / Claude / Cursor / Agent ]
                   │
      (HTTP Header: Authorization: Bearer sk_mcp_...)
      (HTTP Header: MCP-Protocol-Version: 2026-07-28)
                   ▼
  [ FastAPI Gateway (Port 5050) ]
     ├── Endpoint: POST /v1/mcp (Official MCP 2026-07-28 JSON-RPC 2.0)
     ├── Security & Auth (Bearer Token + Sliding Window Rate Limiter)
     ├── SSRF Validator (Pre-request DNS + IP Subnet Filtering)
     ├── Tool 1: web_search (SearXNG / DDG Meta-Search Engine)
     ├── Tool 2: fetch_url (Raw Text Fetcher)
     └── Tool 3: extract_markdown (HTML -> Clean Markdown Converter)
```

---

## 🚀 Quickstart & Docker Installation (< 2 Minutes)

```bash
# 1. Clone Repository
git clone https://github.com/Arbolencio/mcp-web-engine.git
cd mcp-web-engine

# 2. Copy Environment Example
cp .env.example .env

# 3. Launch with Docker Compose
docker compose up -d

# 4. Verify Health Check
curl -s http://localhost:5050/health
# {"status":"ok","environment":"production","searxng_url":"http://host.docker.internal:8082/search","mcp_version":"2026-07-28"}
```

---

## 🔌 Connecting from MCP Clients (Claude Desktop, Cursor, Windsurf, Inspector)

### Standard MCP Config (`claude_desktop_config.json` / Cursor / Windsurf):

```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-fetch",
        "http://YOUR_SERVER_IP:5050/v1/mcp"
      ],
      "env": {
        "AUTHORIZATION": "Bearer YOUR_BETA_KEY_HERE"
      }
    }
  }
}
```

---

## 🛠️ MCP Tools & Protocol Messages (Spec 2026-07-28)

### 1. `tools/list` Discovery
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### 2. `web_search` Tool Call
Performs aggregate multi-engine web search returning structured search results.
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "web_search",
    "arguments": {
      "query": "Model Context Protocol 2026 specification",
      "limit": 5
    }
  }
}
```

### 3. `fetch_url` Tool Call
Fetches raw text content of a web page after SSRF security checks.
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "fetch_url",
    "arguments": {
      "url": "https://news.ycombinator.com",
      "max_bytes": 1048576
    }
  }
}
```

### 4. `extract_markdown` Tool Call
Scrapes a web page and converts HTML into clean, structured Markdown for LLMs.
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "extract_markdown",
    "arguments": {
      "url": "https://fastapi.tiangolo.com"
    }
  }
}
```

---

## 🔑 Managing Beta Keys

Manage API access keys using the CLI helper:

```bash
# Generate 15 Beta Keys
python manage_beta_keys.py generate --count 15

# List active keys
python manage_beta_keys.py list

# Revoke a key
python manage_beta_keys.py revoke --key sk_mcp_beta_...
```

---

## 🛡️ Security & Honest Technical Limits

- **SSRF Hardening:** Blocks `localhost`, loopbacks, private subnets (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), percent-encoding bypasses (`%31%32%37...`), and re-validates `Location` headers on HTTP redirects step-by-step.
- **Rate Limiting:** Default limit of 120 req/min per key.
- **Honest Positioning:** Designed for research, documentation retrieval, and web search. Auth-walled sites requiring login (e.g. private social feeds) are not supported.

---

## 📄 License

MIT License © 2026 MCP Web Engine Contributors.
