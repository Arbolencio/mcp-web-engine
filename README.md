# 🌐 MCP Web Engine & Search Gateway

> **Public HTTPS Specification 2026-07-28 Pure Stateless Core MCP Server for AI Agents**

---

## 🌐 Public Production HTTPS Endpoint

- **Public MCP 2026-07-28 Endpoint:** `https://surveys-networking-titled-middle.trycloudflare.com/v1/mcp`
- **Health Check:** `https://surveys-networking-titled-middle.trycloudflare.com/health`

---

## 📌 What it does & Why it exists

`MCP Web Engine` is a high-performance Model Context Protocol (MCP) server implementing the **MCP Specification 2026-07-28 Pure Stateless Core** (JSON-RPC 2.0 over HTTPS). It provides AI Agents (Claude Desktop, Cursor, Windsurf, MCP Inspector, Hermes Agent) with secure, private access to web search, raw content fetching, and clean HTML-to-Markdown extraction.

### Key Capabilities & Architecture
- **Pure Stateless Core (Spec 2026-07-28):** Zero sessions, zero state, zero initialize handshake required. Every request is completely independent.
- **Protocol Methods:** Implements `server/discover`, `tools/list`, and `tools/call` with standard JSON-RPC 2.0 payloads.
- **Zero Third-Party Tracking:** Powered by an internal SearXNG meta-search engine aggregating 70+ sources with DuckDuckGo fallback.
- **SSRF Hardened:** Pre-request DNS resolution checks prevent agents from accessing internal networks (`localhost`, `127.0.0.1`, `192.168.x.x`, `169.254.169.254`). Step-by-step HTTP 301/302 redirect re-validation.
- **TLS Fingerprinting:** Powered by `curl_cffi` (Chrome 120+ TLS impersonation) for clean research scraping without heavy browser overhead.

---

## 🏗️ Architecture

```
[ MCP Client / Claude / Cursor / Windsurf / Inspector ]
                         │
        (HTTPS Header: Authorization: Bearer sk_mcp_...)
        (HTTPS Header: MCP-Protocol-Version: 2026-07-28)
                         ▼
        [ Cloudflare HTTPS Secure Tunnel ]
                         │
                         ▼
        [ FastAPI Gateway (Port 5050) ]
           ├── Endpoint: POST /v1/mcp (Pure Stateless Core)
           ├── Security & Auth (Bearer Token + Sliding Window Rate Limiter)
           ├── SSRF Validator (Pre-request DNS + IP Subnet Filtering)
           ├── Method 1: server/discover (Server Metadata Discovery)
           ├── Method 2: tools/list (Tools Discovery)
           └── Method 3: tools/call (Tool Execution Engine)
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
curl -s https://surveys-networking-titled-middle.trycloudflare.com/health
# {"status":"ok","environment":"production","searxng_url":"http://host.docker.internal:8082/search","mcp_version":"2026-07-28"}
```

---

## 🔌 Connecting from MCP Clients (Cursor, Windsurf, Inspector, Claude Desktop)

### 1. Cursor / Windsurf / MCP Inspector (Direct HTTPS):
- **Server Endpoint:** `https://surveys-networking-titled-middle.trycloudflare.com/v1/mcp`
- **Headers:**
  - `Authorization: Bearer YOUR_BETA_KEY_HERE`
  - `MCP-Protocol-Version: 2026-07-28`

### 2. Claude Desktop (via `mcp-remote` bridge):
```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://surveys-networking-titled-middle.trycloudflare.com/v1/mcp",
        "--header",
        "Authorization: Bearer YOUR_BETA_KEY_HERE"
      ]
    }
  }
}
```

---

## 🛠️ MCP 2026-07-28 Stateless Protocol Lifecycle

### 1. `server/discover` Discovery
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "server/discover",
  "params": {}
}
```

### 2. `tools/list` Discovery
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

### 3. `tools/call` Execution
```json
{
  "jsonrpc": "2.0",
  "id": 3,
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
# Generate 20 Beta Keys
python manage_beta_keys.py init20

# View Beta User Telemetry
python manage_beta_keys.py telemetry

# Revoke a key by ID
python manage_beta_keys.py revoke --id Beta_001
```

---

## 🛡️ Security & Honest Technical Limits

- **SSRF Hardening:** Blocks `localhost`, loopbacks, private subnets (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), percent-encoding bypasses (`%31%32%37...`), and re-validates `Location` headers on HTTP redirects step-by-step.
- **Rate Limiting:** Default limit of 120 req/min per key.
- **Honest Positioning:** Designed for research, documentation retrieval, and web search. Auth-walled sites requiring login (e.g. private social feeds) are not supported.

---

## 📄 License

MIT License © 2026 MCP Web Engine Contributors.
