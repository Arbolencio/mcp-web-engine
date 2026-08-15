# 🌐 MCP Web Engine & Search Gateway

> **Official Specification 2026-07-28 Streamable HTTP / JSON-RPC 2.0 MCP Server for AI Agents**

---

## 📌 What it does & Why it exists

`MCP Web Engine` is a lightweight, high-performance Model Context Protocol (MCP) server conforming to the **MCP Specification 2026-07-28 (Streamable HTTP & JSON-RPC 2.0 core)**. It provides AI Agents (Claude Desktop, Cursor, Windsurf, MCP Inspector, Hermes Agent) with secure, private access to web search, raw content fetching, and clean HTML-to-Markdown extraction.

### Key Capabilities & Security
- **Official Spec 2026-07-28 Compliant:** Native JSON-RPC 2.0 over Streamable HTTP (`/v1/mcp`) supporting `initialize`, `notifications/initialized`, `tools/list`, and `tools/call` with `Mcp-Session-Id` tracking.
- **Zero Third-Party Tracking:** Powered by an internal SearXNG meta-search engine aggregating 70+ sources with DuckDuckGo fallback.
- **SSRF Hardened:** Pre-request DNS resolution checks prevent agents from accessing internal networks (`localhost`, `127.0.0.1`, `192.168.x.x`, `169.254.169.254`). Step-by-step HTTP 301/302 redirect re-validation.
- **TLS Fingerprinting:** Powered by `curl_cffi` (Chrome 120+ TLS impersonation) for clean research scraping without heavy browser overhead.

---

## 🏗️ Architecture

```
[ MCP Client / Claude / Cursor / Windsurf / Inspector ]
                         │
        (HTTP Header: Authorization: Bearer sk_mcp_...)
        (HTTP Header: Mcp-Session-Id: mcp_sess_...)
        (HTTP Header: MCP-Protocol-Version: 2026-07-28)
                         ▼
        [ FastAPI Gateway (Port 5050) ]
           ├── Endpoint: POST /v1/mcp (Official MCP 2026-07-28 JSON-RPC 2.0)
           ├── Session Engine (Mcp-Session-Id Tracking & State)
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

### 1. Claude Desktop (via `mcp-remote` / bridge):
Since Claude Desktop connects to local stdio processes, use a lightweight bridge to proxy remote Streamable HTTP MCP endpoints:

```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://YOUR_SERVER_IP:5050/v1/mcp",
        "--header",
        "Authorization: Bearer YOUR_BETA_KEY_HERE"
      ]
    }
  }
}
```

### 2. Cursor / Windsurf / MCP Inspector (Direct HTTP/SSE):
Connect directly using the Streamable HTTP endpoint:
- **Server URL:** `http://YOUR_SERVER_IP:5050/v1/mcp`
- **Headers:** `Authorization: Bearer YOUR_BETA_KEY_HERE`

---

## 🛠️ MCP Protocol Lifecycle (Spec 2026-07-28)

### 1. `initialize` Handshake
```json
{
  "jsonrpc": "2.0",
  "id": 0,
  "method": "initialize",
  "params": {
    "protocolVersion": "2026-07-28",
    "capabilities": {},
    "clientInfo": { "name": "claude-desktop", "version": "1.0.0" }
  }
}
```

### 2. `notifications/initialized` Notification
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
```

### 3. `tools/list` Discovery
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### 4. `tools/call` Execution
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
