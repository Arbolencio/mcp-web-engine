# Operating boundaries

- Configure an operator-owned SearXNG backend. Queries go to that backend and its search engines even when DuckDuckGo fallback is disabled. Never accept arbitrary clients' backend URLs as trusted configuration.
- Keep HTTP on loopback or a restricted network. Generate a unique API_KEY (at least 32 characters); terminate TLS at a reverse proxy for remote access. Health is liveness only. HTTP admission limits, beta quotas and per-key tool telemetry persist in SQLite, serializing workers that share the same local file. Set MCP_WEB_ENGINE_STATE_DB to an absolute writable path. This is not multi-host coordination: do not put SQLite on a distributed network mount. Process summary metrics remain process-local. Set MCP_WEB_ENGINE_BETA_KEYS_FILE to the separate operator-managed credential file; telemetry never rewrites that file. Preserve state across container replacement to preserve quotas; deleting database rows resets usage.
- Explicit env files require MCP_WEB_ENGINE_ENV_FILE with an absolute path. Compose itself may interpolate a local .env file; that is Docker Compose behavior, not automatic application env loading. Do not bake secrets into images or npm tarballs.
- The Docker context uses a deny-by-default allowlist for Python source and build metadata. Keep credentials outside src/; review actual artifacts before distribution. Do not put secrets in Python source or README metadata.
- Public fetch validation and redirect checks do not replace firewall egress policy. Restrict cloud metadata, internal services and proxy configuration at the network layer. Treat fetched content as untrusted, including prompt injection.
- uv/npm installation can access package registries and write dependency caches. It is not an execution sandbox. Release-version pins do not lock transitive dependencies. Docker exports the runtime dependency set from `uv.lock` with `uv export --locked --no-dev --no-emit-project`, installs it with pip hash verification, then installs the project without resolving dependencies. Metadata/lock mismatches fail the build. This locks runtime Python dependencies, not base-image tags or isolated build-system dependencies; pin image digests and audit build dependencies for stricter reproducibility.
- The stateless protocol label is project-specific, not an official specification certification. SSE is limited; validate your client's transport requirements. Stdio uses JSON lines rather than Content-Length framing.

## HTTP resource settings

`MAX_CONCURRENT_REQUESTS=16` caps in-flight HTTP requests per process. It is not shared across workers or hosts and is separate from the persisted per-key admission quota. `REQUEST_BODY_TIMEOUT_SEC=10` sets an absolute deadline for receiving the HTTP body; slowly sending another chunk does not reset it. Tune both alongside `MAX_PAYLOAD_BYTES` and reverse-proxy limits for the available memory and workload.

The container runs with UID/GID 1000 and writes state under `/home/appuser/.local/state/mcp-web-engine`. Bind-mounted replacements must be writable by that identity; named volumes inherit the prepared image directory ownership when first populated. Keep the existing volume for upgrades. Health probes are unauthenticated liveness only, not backend readiness or a quota/storage integrity check.

## Verify a local Docker image without touching deployed services

The beta-key management CLI currently uses POSIX `flock` to serialize operator updates and is supported on Linux/macOS. This audit does not establish Windows support for that optional management command; it does not add a Windows-only import to the stdio server.

Compose mounts the named `usage-state` volume for SQLite and operator-managed beta credentials. Container replacement preserves it; `docker compose down -v` explicitly destroys it and resets usage. Back up the volume and never use that command as routine deployment cleanup.

Build a separately tagged image, run it with an ephemeral loopback port and a disposable key, probe /health and protected routes, then remove only that container. Never use compose down against an existing deployment as a test cleanup step.
