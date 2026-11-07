# Security Policy

## Reporting vulnerabilities

Please do not disclose an exploitable vulnerability in a public issue. Use [GitHub private vulnerability reporting](https://github.com/Arbolencio/mcp-web-engine/security/advisories/new) when enabled, or privately contact the repository maintainer to agree on a secure channel before sharing a proof of concept. This repository does not guarantee response times or a security support window.

## Controls and limitations

- Public fetches validate schemes, DNS addresses and redirect destinations to reject private, loopback and reserved networks. These are defense-in-depth controls, not a guarantee against all DNS, proxy, routing or SSRF attacks. Enforce independent egress policy. Operator-configured SearXNG is a deliberate trusted-backend exception.
- Protected HTTP tool endpoints require a Bearer key. Stdio instead inherits the local process's permissions and has no Bearer authentication. `/health` is public liveness information. Authentication does not provide TLS; keep HTTP restricted and use a TLS reverse proxy for remote access.
- The provided Docker image runs as UID/GID 1000; Compose adds `no-new-privileges:true` and a loopback port binding. These are supplied deployment settings, not properties of every installation.
- Quotas and per-key tool telemetry persist in local SQLite. Protect the state volume and the separate operator-managed beta credential file. Do not reset or remove usage data as routine cleanup.
- Search queries reach SearXNG and its upstream engines; optional DuckDuckGo fallback is off by default. Self-hosting and dependency isolation are not privacy guarantees or execution sandboxes. Fetched content is untrusted, including prompt injection.

See [operating boundaries](docs/operations.md) for deployment, persistence and artifact precautions.
