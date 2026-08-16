from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit


class UnsafeUrlError(ValueError):
    """Raised when a URL is not safe for server-side retrieval."""


@dataclass(frozen=True)
class SafeTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    host_header: str
    request_target: str
    addresses: tuple[str, ...]


def normalize_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnsafeUrlError("A URL is required")

    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are supported")
    if not parts.hostname:
        raise UnsafeUrlError("URL must include a hostname")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("URLs containing credentials are not supported")

    scheme = parts.scheme.lower()
    hostname = parts.hostname.rstrip(".").lower()
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrlError("URL contains an invalid port") from exc

    default_port = 443 if scheme == "https" else 80
    if port is not None and port not in {80, 443}:
        raise UnsafeUrlError("Only ports 80 and 443 are supported")

    netloc = hostname
    if ":" in hostname and not hostname.startswith("["):
        netloc = f"[{hostname}]"
    if port is not None and port != default_port:
        netloc = f"{netloc}:{port}"

    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _is_public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_global


def resolve_safe_target(value: str) -> SafeTarget:
    normalized = normalize_url(value)
    parts = urlsplit(normalized)
    hostname = parts.hostname
    assert hostname is not None

    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError("Hostname could not be resolved") from exc

    addresses: list[str] = []
    for result in results:
        ip = result[4][0]
        if ip not in addresses:
            addresses.append(ip)

    if not addresses:
        raise UnsafeUrlError("Hostname did not resolve to an address")
    if any(not _is_public_ip(ip) for ip in addresses):
        raise UnsafeUrlError("Hostname resolves to a non-public address")

    host_header = _host_header(parts, port)
    request_target = parts.path or "/"
    if parts.query:
        request_target += f"?{parts.query}"

    return SafeTarget(
        url=normalized,
        scheme=parts.scheme,
        hostname=hostname,
        port=port,
        host_header=host_header,
        request_target=request_target,
        addresses=tuple(addresses),
    )


def _host_header(parts: SplitResult, port: int) -> str:
    hostname = parts.hostname or ""
    rendered = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if parts.scheme == "https" else 80
    return rendered if port == default_port else f"{rendered}:{port}"
