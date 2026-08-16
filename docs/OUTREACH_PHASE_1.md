# 📩 PLAN DE ADQUISICIÓN Y MENSAJES PERSONALIZADOS — FASE 1 (TOP 5 BETA TESTERS)

---

## 🎯 1. Prospecto 1: `gefsikatsinelou`
- **Proyecto:** [`gefsikatsinelou/MetaSearchMCP`](https://github.com/gefsikatsinelou/MetaSearchMCP) (52 stars)
- **Motivo de Selección:** Ha construido un metabuscador MCP con FastAPI y SearXNG. Es el fit arquitectónico perfecto.
- **Canal de Contacto:** GitHub Issue / Discussion en `gefsikatsinelou/MetaSearchMCP`
- **Beta Key Asignada:** `sk_mcp_beta_d615bc3f0d0f3b304412ac65c3be5c3d` (Cuota: 1.000 reqs)

### ✉️ Mensaje Personalizado:
```markdown
Hi @gefsikatsinelou,

I came across your `MetaSearchMCP` project and really appreciated your architecture using FastAPI and SearXNG for agent workflows.

We've been building `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), an open-source MCP server implementing the pure stateless MCP Spec 2026-07-28 core (`server/discover`, `tools/list`, `tools/call`). It handles multi-engine search via an internal SearXNG gateway + DuckDuckGo fallback, combined with `curl_cffi` (Chrome 120+ TLS impersonation) and strict SSRF pre-request DNS validation.

Since you've worked directly on MCP search gateways, I'd love to get your technical feedback on our HTML-to-Markdown extraction quality and latency.

I generated a dedicated Beta Key for you to test our live HTTPS endpoint:
- Endpoint: https://mcp.trebol.work/v1/mcp
- Header: Authorization: Bearer sk_mcp_beta_d615bc3f0d0f3b304412ac65c3be5c3d (1,000 requests quota)

No pitch—just curious to hear your thoughts if you get a chance to try it with Claude Desktop, Cursor, or your agents!
```

---

## 🎯 2. Prospecto 2: `robbyczgw-cla`
- **Proyecto:** [`robbyczgw-cla/web-search-plus-mcp`](https://github.com/robbyczgw-cla/web-search-plus-mcp)
- **Motivo de Selección:** Apasionado del ruteo de metabúsqueda y la extracción limpia para evitar respuestas inventadas.
- **Canal de Contacto:** GitHub Issue / Discussion en `robbyczgw-cla/web-search-plus-mcp`
- **Beta Key Asignada:** `sk_mcp_beta_55d496a7eb1c5e9334407bc4bc7a3274` (Cuota: 1.000 reqs)

### ✉️ Mensaje Personalizado:
```markdown
Hi @robbyczgw-cla,

Loved your work on `web-search-plus-mcp` and your emphasis on giving AI agents real sources rather than hallucinated answers.

We just launched `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), a privacy-first MCP server conforming strictly to the MCP Spec 2026-07-28 stateless standard. It focuses on zero third-party tracking, fast HTML-to-Markdown extraction (`extract_markdown`), and SSRF-hardened fetching using `curl_cffi` TLS fingerprinting.

Given your experience testing multiple search and extraction providers, I'd really value your honest feedback on our extraction clean-up and search fallback latency.

Here is a free Beta Key to test our live endpoint:
- Endpoint: https://mcp.trebol.work/v1/mcp
- Header: Authorization: Bearer sk_mcp_beta_55d496a7eb1c5e9334407bc4bc7a3274 (1,000 requests quota)

Would love to know how it compares against your multi-provider benchmarks!
```

---

## 🎯 3. Prospecto 3: `Dan1el2109`
- **Proyecto:** [`Dan1el2109/mcp-agent-search-hub`](https://github.com/Dan1el2109/mcp-agent-search-hub)
- **Motivo de Selección:** Curador del MCP Agent Search Hub 2026.
- **Canal de Contacto:** GitHub Issue / PR en `Dan1el2109/mcp-agent-search-hub`
- **Beta Key Asignada:** `sk_mcp_beta_3d1d19889ba0cb1bc0ecb9623e8dd3f2` (Cuota: 1.000 reqs)

### ✉️ Mensaje Personalizado:
```markdown
Hi @Dan1el2109,

I saw your `mcp-agent-search-hub` repository cataloging MCP tools for AI agents in 2026. Great initiative!

We recently open-sourced `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), an SSRF-hardened, self-hostable MCP server for web search (`web_search`), raw fetching (`fetch_url`), and Markdown conversion (`extract_markdown`) following the MCP 2026-07-28 specification.

We'd love to have it listed in your hub if you find it valuable. Here's a dedicated Beta Key so you can test and benchmark the live server:
- Endpoint: https://mcp.trebol.work/v1/mcp
- Header: Authorization: Bearer sk_mcp_beta_3d1d19889ba0cb1bc0ecb9623e8dd3f2 (1,000 requests quota)

Let me know if you run into any issues or have suggestions for the hub integration!
```

---

## 🎯 4. Prospecto 4: `mrkrsl`
- **Proyecto:** [`mrkrsl/web-search-mcp`](https://github.com/mrkrsl/web-search-mcp) (1,085 stars)
- **Motivo de Selección:** Creador de uno de los servidores MCP de búsqueda más populares para LLMs locales.
- **Canal de Contacto:** GitHub Issue en `mrkrsl/web-search-mcp`
- **Beta Key Asignada:** `sk_mcp_beta_a9f143714b870db1fdf4d7f58d044e4d` (Cuota: 1.000 reqs)

### ✉️ Mensaje Personalizado:
```markdown
Hi @mrkrsl,

Kudos on `web-search-mcp`—it's been a staple in the local LLM & MCP community!

We've been working on `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine), a Python/FastAPI implementation built around the pure stateless MCP Spec 2026-07-28 (`server/discover`, `tools/list`, `tools/call`). We focused heavily on SSRF protection (pre-request DNS subnet checks) and zero-tracking search using internal SearXNG + DuckDuckGo fallback.

If you're interested in benchmarking your local setup against a hosted/streamable HTTP gateway, I set up a dedicated test key for you:
- Endpoint: https://mcp.trebol.work/v1/mcp
- Header: Authorization: Bearer sk_mcp_beta_a9f143714b870db1fdf4d7f58d044e4d (1,000 requests quota)

Any feedback on latency or Markdown formatting for local agent setups like Claude Code or Cursor would be awesome!
```

---

## 🎯 5. Prospecto 5: `pskill9`
- **Proyecto:** [`pskill9/web-search`](https://github.com/pskill9/web-search) (465 stars)
- **Motivo de Selección:** Creador de un servidor MCP de búsqueda web sin necesidad de claves de API de pago.
- **Canal de Contacto:** GitHub Issue en `pskill9/web-search`
- **Beta Key Asignada:** `sk_mcp_beta_7d42cf3896dfa2202613d52030ab1439` (Cuota: 1.000 reqs)

### ✉️ Mensaje Personalizado:
```markdown
Hi @pskill9,

Great work on `web-search`—providing free web search for MCP without requiring paid API keys is crucial for agent adoption.

We built `MCP Web Engine` (https://github.com/Arbolencio/mcp-web-engine) with a similar philosophy: privacy-first, zero third-party tracking, and zero paid API keys needed, powered by SearXNG + DuckDuckGo fallback and `curl_cffi` TLS impersonation.

I'd love your thoughts on our `extract_markdown` tool and search latency over Streamable HTTP (MCP Spec 2026-07-28).

Here is a dedicated Beta Key to test the live service:
- Endpoint: https://mcp.trebol.work/v1/mcp
- Header: Authorization: Bearer sk_mcp_beta_7d42cf3896dfa2202613d52030ab1439 (1,000 requests quota)

Looking forward to your feedback!
```
