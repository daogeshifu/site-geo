from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import AppError
from app.utils.url_utils import normalize_url


def _is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.is_global:
        return True
    benchmark_proxy_range = ipaddress.ip_network("198.18.0.0/15")
    return bool(settings.allow_benchmark_proxy_ips and address in benchmark_proxy_range)


async def normalize_public_url(url: str) -> str:
    """Normalize a user supplied URL and reject SSRF-sensitive destinations."""
    try:
        raw = url.strip()
        scheme = re.match(r"^([a-z][a-z0-9+.\-]*)://", raw, re.I)
        if scheme:
            protocol = scheme[1].lower()
            if protocol not in {"http", "https"}:
                raise ValueError("Only http and https URLs are supported")
            raw = protocol + raw[len(scheme[1]):]
        normalized = normalize_url(raw)
        parsed = urlparse(normalized)
        port = parsed.port
    except ValueError as exc:
        raise AppError(400, str(exc)) from exc

    if parsed.scheme not in {"http", "https"}:
        raise AppError(400, "Only http and https URLs are supported")
    if parsed.username or parsed.password:
        raise AppError(400, "URLs containing credentials are not supported")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise AppError(400, "URL hostname is required")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise AppError(400, "Local network URLs are not allowed")

    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise AppError(400, f"Unable to resolve hostname: {hostname}") from exc

    addresses = {record[4][0].split("%", 1)[0] for record in records}
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise AppError(400, "Private, reserved, or local network URLs are not allowed")
    return normalized
