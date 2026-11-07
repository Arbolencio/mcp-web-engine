"""
Hardened Security Module: SSRF Protection, IP/DNS Validation, Multi-Key Auth (Master & Beta Keys) & Rate Limiting
"""

import hashlib
import hmac
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import state_store
from .config import settings

security_bearer = HTTPBearer(auto_error=False)
_security_credentials = Security(security_bearer)

# Compatibility/debug mirror only; clearing it NEVER resets durable usage.
rate_limit_records = {}
_rate_lock = threading.RLock()
MAX_RATE_BUCKETS = 4096
BETA_KEYS_FILE = str(state_store.beta_keys_path())


def _secret_matches(token, expected):
    return (
        isinstance(token, str)
        and isinstance(expected, str)
        and bool(token)
        and bool(expected)
        and len(token) <= 1024
        and not any(0xD800 <= ord(c) <= 0xDFFF for c in token + expected)
        and hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8"))
    )


def _is_master_key(token):
    return _secret_matches(token, settings.API_KEY)


def _key_id(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _beta_record(token):
    """Re-read operator state on every admission; malformed state fails closed."""
    if not isinstance(token, str) or not token or len(token) > 1024:
        return None
    try:
        with open(BETA_KEYS_FILE, "r", encoding="utf-8") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return None
        keys = json.loads(raw)
        if not isinstance(keys, dict):
            return None
        record = next(
            (value for key, value in keys.items() if _secret_matches(token, key)), None
        )
        if not isinstance(record, dict) or record.get("status") != "active":
            return None
        limit = record.get("limit")
        rate = record.get("rate_limit", settings.RATE_LIMIT_PER_MINUTE)
        telemetry = record.get("telemetry", {})
        if not isinstance(telemetry, dict):
            return None
        requests = telemetry.get("requests", 0)
        if any(
            type(value) is not int or value < 0 for value in (limit, rate, requests)
        ):
            return None
        if rate == 0:
            return None
        expires = record.get("expires_at")
        if expires is not None:
            if not isinstance(expires, str):
                return None
            expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                return None
        return record
    except (OSError, ValueError, TypeError, AttributeError, RecursionError):
        return None


def is_beta_key_valid(token: str) -> bool:
    record = _beta_record(token)
    if record is None:
        return False
    try:
        usage = state_store.read_usage(_key_id(token))
    except state_store.StateUnavailable:
        return False
    return max(record.get("telemetry", {}).get("requests", 0),
               usage.get("admissions", 0)) < record["limit"]


# Stable special-purpose exclusions supplement ipaddress's versioned registry.
# Conservative policy also excludes globally reachable anycast exceptions here.
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.88.99.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
        "2001::/23",
        "2001:db8::/32",
        "3fff::/20",
    )
)
# IPv6 transition mechanisms can route a global-looking address into IPv4.
TRANSITION_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "64:ff9b::/96",
        "64:ff9b:1::/48",
        "2001::/32",
        "2002::/16",
    )
)
FORBIDDEN_HOSTNAMES = {"localhost", "loopback", "broadcasthost", "local"}


def is_ip_private(ip_str: str) -> bool:
    """Historical API name: True means *not a public unicast destination*."""
    try:
        ip = ipaddress.ip_address(int(ip_str) if ip_str.isdigit() else ip_str)
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped is not None:
                return is_ip_private(str(ip.ipv4_mapped))
            if any(ip in net for net in TRANSITION_NETWORKS):
                return True
            if ip not in ipaddress.ip_network("2000::/3"):
                return True
        if any(ip.version == net.version and ip in net for net in PRIVATE_NETWORKS):
            return True
        return (
            not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified
        )
    except ValueError:
        return False


def _url_error(
    code="INVALID_URL", message="Malformed or ambiguous HTTP URL.", status_code=400
):
    return HTTPException(
        status_code=status_code, detail={"error": code, "message": message}
    )


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    hostname: str
    port: int
    addresses: tuple

    @property
    def resolve_entry(self):
        # One validated address, no DNS fallback. URL retains Host and TLS SNI.
        address = self.addresses[0]
        if ":" in address:
            address = f"[{address}]"
        host = f"[{self.hostname}]" if ":" in self.hostname else self.hostname
        return f"{host}:{self.port}:{address}"


def _parse_http_url(url_str):
    if not isinstance(url_str, str) or not url_str or len(url_str) > 16384:
        raise _url_error()
    # urlsplit silently removes controls/leading whitespace; libcurl need not.
    if "\\" in url_str or any(
        ord(c) <= 32 or ord(c) == 127 or c.isspace() for c in url_str
    ):
        raise _url_error()
    try:
        parsed = urllib.parse.urlsplit(url_str)
        if parsed.scheme not in ("http", "https"):
            raise _url_error("INVALID_SCHEME", "Only http/https are supported.")
        # Never decode authorities or accept userinfo/IPv6 zone identifiers.
        if not parsed.netloc or any(c in parsed.netloc for c in ("%", "@")):
            raise _url_error()
        hostname = parsed.hostname
        port = parsed.port
        if not hostname or port == 0 or parsed.netloc.endswith(":"):
            raise _url_error()
        port = port or (443 if parsed.scheme == "https" else 80)
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            hostname = hostname.encode("idna").decode("ascii").lower().rstrip(".")
            labels = hostname.split(".")
            if (
                not hostname
                or len(hostname) > 253
                or any(
                    not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in labels
                )
            ):
                raise _url_error()
            # libcurl interprets legacy numeric IPv4 as literals, ignoring DNS.
            try:
                socket.inet_aton(hostname)
            except OSError:
                pass
            else:
                raise _url_error()
        else:
            hostname = str(ip)
        authority = f"[{hostname}]" if ":" in hostname else hostname
        if parsed.port is not None:
            authority += f":{port}"
        # Encode Unicode path/query once. Never unquote URL data or authority.
        path = urllib.parse.quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        query = urllib.parse.quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~[]")
        canonical = urllib.parse.urlunsplit((parsed.scheme, authority, path, query, ""))
        return canonical, hostname, port
    except (ValueError, UnicodeError):
        raise _url_error() from None


def resolve_ssrf_target(url_str: str) -> ValidatedTarget:
    """Resolve once; fetchers MUST pin these exact addresses into the transport."""
    canonical, hostname, port = _parse_http_url(url_str)
    if hostname in FORBIDDEN_HOSTNAMES or hostname.endswith((".local", ".localhost")):
        raise _url_error("SSRF_BLOCKED", "Local hostname is blocked.", 403)
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except OSError:
            raise _url_error(
                "DNS_RESOLUTION_FAILED", "Could not resolve target hostname."
            ) from None
        addresses = tuple(dict.fromkeys(record[4][0] for record in records))
    else:
        addresses = (str(literal),)
    if not addresses:
        raise _url_error("DNS_RESOLUTION_FAILED", "No destination addresses returned.")
    for address in addresses:
        try:
            ipaddress.ip_address(address)
        except ValueError:
            raise _url_error(
                "SSRF_BLOCKED", "Invalid destination address.", 403
            ) from None
        if is_ip_private(address):
            raise _url_error(
                "SSRF_BLOCKED", "Non-public destination address is blocked.", 403
            )
    return ValidatedTarget(canonical, hostname, port, addresses)


def validate_ssrf_url(url_str: str) -> str:
    """Compatibility API; fetching requires resolve_ssrf_target, not this alone."""
    return resolve_ssrf_target(url_str).url


def verify_api_key(auth: HTTPAuthorizationCredentials = _security_credentials):
    if (
        not auth
        or not auth.credentials
        or not isinstance(auth.scheme, str)
        or auth.scheme.lower() != "bearer"
    ):
        raise HTTPException(
            401,
            detail={"error": "UNAUTHORIZED", "message": "Invalid or missing API key."},
        )
    token = auth.credentials
    if _is_master_key(token) or is_beta_key_valid(token):
        return token
    raise HTTPException(
        401, detail={"error": "UNAUTHORIZED", "message": "Invalid or revoked API key."}
    )


def verify_master_api_key(auth: HTTPAuthorizationCredentials = _security_credentials):
    """Dependency for operator-only telemetry/metrics. Wire at the route layer."""
    token = verify_api_key(auth)
    if not _is_master_key(token):
        raise HTTPException(403, detail={"error": "ADMIN_REQUIRED"})
    return token


def check_rate_limit(api_key: str):
    """Common durable admission for HTTP transports; one call per request.

    Quota counts admitted requests, not tools within a batch. No authorization
    JSON is ever written. All local workers must share MCP_WEB_ENGINE_STATE_DB.
    """
    master = _is_master_key(api_key)
    record = None if master else _beta_record(api_key)
    if not master and record is None:
        raise HTTPException(401, detail={"error": "UNAUTHORIZED"})
    key = _key_id(api_key)
    rate = settings.RATE_LIMIT_PER_MINUTE
    if record is not None:
        rate = min(rate, record.get("rate_limit", rate))
    try:
        state_store.admit(
            key, rate, quota=record["limit"] if record is not None else None,
            baseline=record.get("telemetry", {}).get("requests", 0) if record is not None else 0,
            capacity=MAX_RATE_BUCKETS, now=time.time(),
        )
    except state_store.AdmissionDenied as exc:
        raise HTTPException(429, detail={"error": exc.code}) from None
    except state_store.StateUnavailable:
        raise HTTPException(503, detail={"error": "USAGE_STATE_UNAVAILABLE"}) from None
    with _rate_lock:
        if len(rate_limit_records) < MAX_RATE_BUCKETS or key in rate_limit_records:
            rate_limit_records[key] = True
