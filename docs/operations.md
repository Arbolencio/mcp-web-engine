# Operating boundaries

- Configure an operator-owned SearXNG backend. Queries go to that backend and its search engines even when DuckDuckGo fallback is disabled. Never accept arbitrary clients' backend URLs as trusted configuration.
- Keep HTTP on loopback or a restricted network. Generate a unique API_KEY (at least 32 characters); terminate TLS at a reverse proxy for remote access. Health is liveness only. HTTP admission limits, beta quotas and per-key tool telemetry persist in SQLite, serializing workers that share the same local file. Set MCP_WEB_ENGINE_STATE_DB to an absolute writable path. This is not multi-host coordination: do not put SQLite on a distributed network mount. Process summary metrics remain process-local. Set MCP_WEB_ENGINE_BETA_KEYS_FILE to the separate operator-managed credential file; telemetry never rewrites that file. Preserve state across container replacement to preserve quotas; deleting database rows resets usage.
- Explicit env files require MCP_WEB_ENGINE_ENV_FILE with an absolute path. Compose itself may interpolate a local .env file; that is Docker Compose behavior, not automatic application env loading. Do not bake secrets into images or npm tarballs.
- The Docker context uses a deny-by-default allowlist for Python source and build metadata. Keep credentials outside src/; review actual artifacts before distribution. Do not put secrets in Python source or README metadata.
- Public fetch validation and redirect checks do not replace firewall egress policy. Restrict cloud metadata, internal services and proxy configuration at the network layer. Treat fetched content as untrusted, including prompt injection.
- uv/npm installation can access package registries and write dependency caches. It is not an execution sandbox. Pin and audit dependencies for reproducible deployments.
- The stateless protocol label is project-specific, not an official specification certification. SSE is limited; validate your client's transport requirements. Stdio uses JSON lines rather than Content-Length framing.

## Verify a local Docker image without touching deployed services

Compose mounts the named `usage-state` volume for SQLite and operator-managed beta credentials. Container replacement preserves it; `docker compose down -v` explicitly destroys it and resets usage. Back up the volume and never use that command as routine deployment cleanup.

Build a separately tagged image, run it with an ephemeral loopback port and a disposable key, probe /health and protected routes, then remove only that container. Never use compose down against an existing deployment as a test cleanup step.
