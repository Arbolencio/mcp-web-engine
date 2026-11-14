# Changelog

## 1.2.2 — 2026-11-14

- Add a standalone local Docker Compose stack including SearXNG with JSON output
  enabled, loopback-only host ports, a pinned SearXNG image and persistent state.
  The existing Compose setup for an external search backend remains available.
- Add an opt-in live probe for search, public-page fetch, Markdown extraction,
  HTTP authentication and loopback rejection.
- Add the architecture diagram, README navigation, troubleshooting and links to
  contributor/security policies. Use absolute documentation links and a PNG
  diagram so the package README can render outside GitHub.
- Declare the Glama maintainer in `glama.json`.
- Add a manual, tag-scoped release workflow that builds and tests artifacts
  before publishing to PyPI and npm through separately configured trusted
  publishers. Include the changelog and contributor/security policies in npm.

The server's tool behavior is unchanged from 1.2.1. The recorded demo remains a
capture of public release 1.2.1; its transcript and media have not been rewritten.

## 1.2.1

- Fix HTTP body deadlines, concurrency limits, Unicode JSON-RPC responses and
  event-loop blocking in state access.
- Improve search response handling, URL normalization, extraction, authorization,
  log bounds and persistent quota accounting.
- Repair distribution details and verify installed npm launchers on
  Windows/macOS/Linux. See
  [the runtime/distribution review](https://github.com/Arbolencio/mcp-web-engine/pull/2).

## 1.2.0

- Consolidate the src implementation; harden public fetching with canonical URL
  validation, public-address checks, connection pinning, redirect checks and
  resource limits.
- Persist HTTP quotas in SQLite, require an operator-generated HTTP key and
  repair npm/Docker launch paths. See
  [the hardening review](https://github.com/Arbolencio/mcp-web-engine/pull/1).
