"""URL validation and SSRF protection.

Permits only HTTP/HTTPS on ports 80/443, rejects userinfo, localhost,
private/loopback/link-local/multicast/reserved/unspecified addresses,
IPv4-mapped IPv6, carrier-grade NAT, and unusual IP representations.

Uses ipaddress for IP checks (not string matching) and DNS resolution to
inspect every returned address for global routability.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import List, Set
from urllib.parse import urlparse

from pydantic import AnyUrl

from app.errors import InvalidURLError, SSRFError

# Allowed schemes and ports.
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}

# Local-only hostnames that must never be reached.
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "::",
    "ip6-localhost",
    "ip6-loopback",
    ".local",
    ".internal",
    ".invalid",
    ".test",
    ".example",
    ".example.com",
    ".localhost",
}

# IP networks that are not globally routable (RFC 1918, RFC 5735, RFC 4193,
# RFC 6598, RFC 4291, etc.).
PRIVATE_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),        # unspecified / "this network"
    ipaddress.ip_network("10.0.0.0/8"),       # private
    ipaddress.ip_network("100.64.0.0/10"),    # carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("169.254.0.0/16"),   # link-local (incl. AWS metadata)
    ipaddress.ip_network("172.16.0.0/12"),    # private
    ipaddress.ip_network("192.0.0.0/24"),     # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),     # documentation / TEST-NET
    ipaddress.ip_network("192.168.0.0/16"),   # private
    ipaddress.ip_network("198.18.0.0/15"),    # benchmarking
    ipaddress.ip_network("198.51.100.0/24"),  # documentation / TEST-NET
    ipaddress.ip_network("203.0.113.0/24"),   # documentation / TEST-NET
    ipaddress.ip_network("224.0.0.0/4"),      # multicast
    ipaddress.ip_network("240.0.0.0/4"),      # reserved
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
    ipaddress.ip_network("ff00::/8"),         # IPv6 multicast
    ipaddress.ip_network("::ffff:0:0/96"),    # IPv4-mapped IPv6
]


def _is_private_ip(host: str) -> bool:
    """Return True if `host` is a private / non-globally-routable IP literal."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in PRIVATE_NETWORKS)


def _resolve_host(host: str) -> List[str]:
    """Resolve a hostname to a list of IP address strings using DNS."""
    try:
        infos = socket.getaddrinfo(
            host, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        return []
    ips: Set[str] = set()
    for info in infos:
        # sockaddr: (address, port) for IPv4; (address, port, flowinfo, scopeid) for IPv6
        addr = info[4][0]
        ips.add(addr)
    return list(ips)


def _host_is_blocked(host: str) -> bool:
    """Check if a hostname or IP literal is blocked by name or resolved IP."""
    host_lower = host.lower()

    # Block known local-only hostnames by name (including suffix match for .local etc.).
    if host_lower in BLOCKED_HOSTNAMES:
        return True
    for suffix in (".local", ".internal", ".invalid", ".test", ".example", ".localhost"):
        if host_lower.endswith(suffix):
            return True

    # If the host is a literal IP, check it directly.
    if _is_private_ip(host):
        return True

    # Resolve the hostname and check every returned IP (DNS-rebinding protection).
    for ip in _resolve_host(host):
        if _is_private_ip(ip):
            return True
        if ip in {"127.0.0.1", "0.0.0.0", "::1"}:
            return True

    return False


def _parse_port(url: str) -> int:
    """Extract the port from a URL string, defaulting by scheme."""
    parsed = urlparse(url)
    if parsed.port is not None:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def validate_url(raw_url: str) -> str:
    """Validate a URL and return its normalized string form.

    Raises ValueError with a descriptive message for any invalid or blocked URL.
    """
    if not raw_url or not raw_url.strip():
        raise InvalidURLError("URL is required.")

    raw_url = raw_url.strip()

    # Reject URL userinfo (user:password@host).
    if "@" in raw_url.split("//", 1)[-1].split("/", 1)[0]:
        raise InvalidURLError("URL credentials (userinfo) are not allowed.")

    # Basic structural validation via Pydantic AnyUrl.
    try:
        parsed = AnyUrl(raw_url)
    except Exception as exc:
        raise InvalidURLError(f"Invalid URL format: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError("Only http:// and https:// URLs are supported.")

    port = _parse_port(raw_url)
    if port not in ALLOWED_PORTS:
        raise InvalidURLError(f"Port {port} is not allowed. Only ports 80 and 443 are supported.")

    host = parsed.host or ""
    if not host:
        raise InvalidURLError("URL must include a hostname.")

    host_lower = host.lower()

    if _host_is_blocked(host):
        raise SSRFError(f"Access to internal address {host} is not allowed.")

    return str(parsed)
