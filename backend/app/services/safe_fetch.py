"""Bounded HTTP client for destinations supplied by users.

Connections are made to a validated DNS result (not the hostname), while the
original Host header and TLS SNI are retained. Redirects are handled manually
so each destination is resolved and checked again.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(8.0, connect=3.0)
DEFAULT_MAX_BYTES = 512 * 1024
DEFAULT_CONTENT_TYPES = frozenset(
    {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml", "text/plain", "application/json"}
)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class SafeFetchError(ValueError):
    """Raised when a user-controlled URL violates outbound-fetch policy."""


def _validate_address(value: str) -> str:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError as exc:
        raise SafeFetchError("Destination did not resolve to an IP address") from exc
    if not address.is_global:
        raise SafeFetchError("Destination resolves to a non-public IP address")
    return str(address)


async def _resolve_public(host: str, port: int) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            records = await loop.run_in_executor(
                None, lambda: socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            )
        except OSError as exc:
            raise SafeFetchError("Destination DNS resolution failed") from exc
        addresses = sorted({record[4][0] for record in records})
    else:
        addresses = [str(literal)]
    if not addresses:
        raise SafeFetchError("Destination did not resolve")
    # Reject the hostname if any answer is unsafe; do not pick only its public answer.
    return [_validate_address(address) for address in addresses]


def _pinned_url(url: str, address: str) -> tuple[str, str, str]:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise SafeFetchError("Only absolute HTTP(S) URLs are supported")
    if parts.username is not None or parts.password is not None:
        raise SafeFetchError("URL credentials are not allowed")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise SafeFetchError("Invalid destination port") from exc
    if not (1 <= port <= 65535):
        raise SafeFetchError("Invalid destination port")
    netloc = f"[{address}]" if ":" in address else address
    if (parts.scheme, port) not in {("http", 80), ("https", 443)}:
        netloc = f"{netloc}:{port}"
    pinned = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    default_port = 443 if parts.scheme == "https" else 80
    original_host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    host_header = original_host if port == default_port else f"{original_host}:{port}"
    return pinned, host_header, parts.hostname


async def safe_fetch(
    url: str,
    *,
    method: str = "GET",
    json: object | None = None,
    headers: dict[str, str] | None = None,
    allowed_content_types: frozenset[str] = DEFAULT_CONTENT_TYPES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    max_redirects: int = 3,
) -> bytes:
    """Fetch a bounded response from a public destination with validated redirects."""
    current = url.strip()
    current_method = method.upper()
    payload = json
    for redirect_index in range(max_redirects + 1):
        parts = urlsplit(current)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise SafeFetchError("Only absolute HTTP(S) URLs are supported")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        addresses = await _resolve_public(parts.hostname, port)
        pinned, host_header, hostname = _pinned_url(current, addresses[0])
        req_headers = {"User-Agent": "SiliconPulse/1.0", **(headers or {})}
        req_headers["Host"] = host_header
        # httpcore uses this extension for SNI and certificate hostname validation.
        extensions = {"sni_hostname": hostname.encode("ascii")}

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            async with client.stream(
                current_method,
                pinned,
                json=payload,
                headers=req_headers,
                extensions=extensions,
            ) as response:
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location or redirect_index >= max_redirects:
                        raise SafeFetchError("Redirect limit exceeded or missing Location")
                    if current_method not in {"GET", "HEAD"} and response.status_code not in {307, 308}:
                        raise SafeFetchError("Unsafe method-changing redirect rejected")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if response.status_code != 204 and content_type not in allowed_content_types:
                    raise SafeFetchError("Response content type is not allowed")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise SafeFetchError("Response exceeds maximum size")
                return bytes(body)
    raise SafeFetchError("Redirect limit exceeded")


def safe_fetch_sync(*args, **kwargs) -> bytes:
    """Sync bridge for scheduler code and async route handlers using sync services."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(safe_fetch(*args, **kwargs))
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, safe_fetch(*args, **kwargs)).result()
