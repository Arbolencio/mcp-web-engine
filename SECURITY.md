# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability (such as a potential SSRF bypass, authentication flaw, or denial of service), please **DO NOT** open a public issue.

Instead, please report it privately to the maintainers with a proof of concept.

## Security Features

- **SSRF Protection:** Pre-request DNS resolution verification blocking private subnets (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`, IPv6 loopbacks, and percent-encoded IP bypasses).
- **Step-by-Step Redirect Re-Validation:** All HTTP 301/302 redirects are validated against SSRF prior to following.
- **Authentication:** All MCP tool endpoints require Bearer API key authorization.
- **Docker Hardening:** Runs under non-root UID 1000 with `no-new-privileges:true`.
