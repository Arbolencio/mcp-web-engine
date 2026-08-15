"""
Hardened Security Module: SSRF Protection, IP/DNS Validation, Multi-Key Auth (Master & Beta Keys) & Rate Limiting
"""
import ipaddress
import socket
import time
import os
import json
import urllib.parse
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings

security_bearer = HTTPBearer(auto_error=False)

rate_limit_records = {}
BETA_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beta_keys.json")

def is_beta_key_valid(token: str) -> bool:
    """
    Checks if a token is an active Beta Key in beta_keys.json.
    """
    if not os.path.exists(BETA_KEYS_FILE):
        return False
    try:
        with open(BETA_KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
            if token in keys and keys[token].get("status") == "active":
                return True
    except Exception:
        pass
    return False

# Reserved Subnets for SSRF Protection
PRIVATE_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10")
]

FORBIDDEN_HOSTNAMES = {"localhost", "loopback", "broadcasthost", "local", "0.0.0.0", "127.0.0.1", "::1"}

def is_ip_private(ip_str: str) -> bool:
    try:
        if ip_str.isdigit():
            ip_obj = ipaddress.ip_address(int(ip_str))
        else:
            ip_obj = ipaddress.ip_address(ip_str)

        for net in PRIVATE_NETWORKS:
            if ip_obj in net:
                return True
        return False
    except ValueError:
        return False

def validate_ssrf_url(url_str: str) -> str:
    if not url_str or not isinstance(url_str, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_URL", "message": "URL must be a non-empty string."}
        )

    unquoted_url = urllib.parse.unquote(url_str)
    
    try:
        parsed = urllib.parse.urlparse(unquoted_url)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_URL", "message": f"URL '{url_str}' is unparseable."}
        )

    if parsed.scheme not in ["http", "https"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCHEME", "message": f"Scheme '{parsed.scheme}' not allowed. Only http/https supported."}
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MISSING_HOSTNAME", "message": "URL must contain a valid hostname."}
        )

    clean_host = hostname.lower().strip(".")

    if clean_host in FORBIDDEN_HOSTNAMES or clean_host.endswith(".local"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "SSRF_BLOCKED", "message": f"Access to hostname '{clean_host}' is blocked (SSRF protection)."}
        )

    if is_ip_private(clean_host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "SSRF_BLOCKED", "message": f"Access to private IP '{clean_host}' is blocked."}
        )

    try:
        ip_addresses = socket.getaddrinfo(clean_host, None)
    except socket.gaierror:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "DNS_RESOLUTION_FAILED", "message": f"Could not resolve hostname '{clean_host}'."}
        )

    for item in ip_addresses:
        resolved_ip = item[4][0]
        if is_ip_private(resolved_ip):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "SSRF_BLOCKED", "message": f"URL resolves to private/loopback IP address '{resolved_ip}' which is blocked."}
            )

    return url_str

def verify_api_key(auth: HTTPAuthorizationCredentials = Security(security_bearer)):
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "Invalid or missing API key."}
        )

    token = auth.credentials
    # Valid if matches Master API_KEY or any active Beta Key
    if token == settings.API_KEY or is_beta_key_valid(token):
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "UNAUTHORIZED", "message": "Invalid or revoked API key."}
    )

def check_rate_limit(api_key: str):
    now = time.time()
    window_start = now - 60.0

    if api_key not in rate_limit_records:
        rate_limit_records[api_key] = []

    rate_limit_records[api_key] = [t for t in rate_limit_records[api_key] if t > window_start]

    if len(rate_limit_records[api_key]) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": f"Rate limit of {settings.RATE_LIMIT_PER_MINUTE} req/min exceeded."}
        )

    rate_limit_records[api_key].append(now)
