# 📩 PLAN DE ADQUISICIÓN Y MENSAJES PERSONALIZADOS (OPT-IN CONSERVADOR) — FASE 1

> **Regla de Seguridad & Conversión:** NO publicar claves API en repositorios públicos. Solicitar confirmación de interés (Opt-In) y entregar la Beta Key de forma privada tras su respuesta.

---

## 🎯 1. Prospecto 1: `gefsikatsinelou`
- **Proyecto:** [`gefsikatsinelou/MetaSearchMCP`](https://github.com/gefsikatsinelou/MetaSearchMCP) (52 stars)
- **Canal de Contacto:** [Abrir Nuevo Issue / Discussion en MetaSearchMCP](https://github.com/gefsikatsinelou/MetaSearchMCP/issues/new)
- **Título Sugerido:** `Feedback / Benchmarking MCP Web Engine (Stateless 2026-07-28 Server)`

### ✉️ Mensaje Personalizado (Sin Token):
```markdown
Hi @gefsikatsinelou,

I came across your `MetaSearchMCP` project and really appreciated your architecture using FastAPI and SearXNG for agent workflows.

We've been building `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), an open-source MCP server implementing the pure stateless MCP Spec 2026-07-28 core (`server/discover`, `tools/list`, `tools/call`). It handles multi-engine search via an internal SearXNG gateway + DuckDuckGo fallback, combined with `curl_cffi` (Chrome 120+ TLS impersonation) and strict SSRF pre-request DNS validation.

Since you've worked directly on MCP search gateways, I'd love to get your technical feedback on our HTML-to-Markdown extraction quality and latency over Streamable HTTP.

If you'd be interested in testing/benchmarking our live HTTPS endpoint with Claude Desktop, Cursor, or your agents, let me know and I'll send over a free Beta Key (1,000 requests quota)!

No pitch—just curious to hear your thoughts if you're open to comparing notes.
```

---

## 🎯 2. Prospecto 2: `robbyczgw-cla`
- **Proyecto:** [`robbyczgw-cla/web-search-plus-mcp`](https://github.com/robbyczgw-cla/web-search-plus-mcp)
- **Canal de Contacto:** [Abrir Nuevo Issue en web-search-plus-mcp](https://github.com/robbyczgw-cla/web-search-plus-mcp/issues/new)
- **Título Sugerido:** `Testing MCP Web Engine extraction latency & fallbacks`

### ✉️ Mensaje Personalizado (Sin Token):
```markdown
Hi @robbyczgw-cla,

Loved your work on `web-search-plus-mcp` and your emphasis on giving AI agents real sources rather than hallucinated answers.

We just launched `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), a privacy-first MCP server conforming strictly to the MCP Spec 2026-07-28 stateless standard. It focuses on zero third-party tracking, fast HTML-to-Markdown extraction (`extract_markdown`), and SSRF-hardened fetching using `curl_cffi` TLS fingerprinting.

Given your experience testing multiple search and extraction providers, I'd really value your honest feedback on our extraction clean-up and search fallback latency.

Let me know if you'd like a free Beta Key (1,000 requests quota) to benchmark our live endpoint against your multi-provider setup, and I'll pass one over!
```

---

## 🎯 3. Prospecto 3: `Dan1el2109`
- **Proyecto:** [`Dan1el2109/mcp-agent-search-hub`](https://github.com/Dan1el2109/mcp-agent-search-hub)
- **Canal de Contacto:** [Abrir Nuevo Issue en mcp-agent-search-hub](https://github.com/Dan1el2109/mcp-agent-search-hub/issues/new)
- **Título Sugerido:** `Adding MCP Web Engine to MCP Agent Search Hub`

### ✉️ Mensaje Personalizado (Sin Token):
```markdown
Hi @Dan1el2109,

I saw your `mcp-agent-search-hub` repository cataloging MCP tools for AI agents in 2026. Great initiative!

We recently open-sourced `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), an SSRF-hardened, self-hostable MCP server for web search (`web_search`), raw fetching (`fetch_url`), and Markdown conversion (`extract_markdown`) following the MCP 2026-07-28 specification.

We'd love to have it listed in your hub if you find it valuable. If you'd like to test and benchmark the live server first, let me know and I'll generate a free Beta Key (1,000 requests quota) for you.

Looking forward to hearing your thoughts!
```

---

## 🎯 4. Prospecto 4: `mrkrsl`
- **Proyecto:** [`mrkrsl/web-search-mcp`](https://github.com/mrkrsl/web-search-mcp) (1,085 stars)
- **Canal de Contacto:** [Abrir Nuevo Issue en web-search-mcp](https://github.com/mrkrsl/web-search-mcp/issues/new)
- **Título Sugerido:** `Benchmarking local web-search-mcp vs Streamable HTTP gateway`

### ✉️ Mensaje Personalizado (Sin Token):
```markdown
Hi @mrkrsl,

Kudos on `web-search-mcp`—it's been a staple in the local LLM & MCP community!

We've been working on `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), a Python/FastAPI implementation built around the pure stateless MCP Spec 2026-07-28 (`server/discover`, `tools/list`, `tools/call`). We focused heavily on SSRF protection (pre-request DNS subnet checks) and zero-tracking search using internal SearXNG + DuckDuckGo fallback.

If you're interested in benchmarking your local setup against a hosted/streamable HTTP gateway, let me know and I'll send over a free test key (1,000 requests quota).

Any feedback on latency or Markdown formatting for local agent setups like Claude Code or Cursor would be awesome!
```

---

## 🎯 5. Prospecto 5: `pskill9`
- **Proyecto:** [`pskill9/web-search`](https://github.com/pskill9/web-search) (465 stars)
- **Canal de Contacto:** [Abrir Nuevo Issue en web-search](https://github.com/pskill9/web-search/issues/new)
- **Título Sugerido:** `Free MCP Web Engine test key & feedback`

### ✉️ Mensaje Personalizado (Sin Token):
```markdown
Hi @pskill9,

Great work on `web-search`—providing free web search for MCP without requiring paid API keys is crucial for agent adoption.

We built `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine) with a similar philosophy: privacy-first, zero third-party tracking, and zero paid API keys needed, powered by SearXNG + DuckDuckGo fallback and `curl_cffi` TLS impersonation.

I'd love your thoughts on our `extract_markdown` tool and search latency over Streamable HTTP (MCP Spec 2026-07-28).

If you're interested in testing the live endpoint, reply here or reach out and I'll send you a free Beta Key (1,000 requests quota)!
```
