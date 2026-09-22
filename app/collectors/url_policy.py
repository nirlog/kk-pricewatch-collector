"""Baseline outbound URL policy for browser navigation.

DNS is checked immediately before navigation. This reduces SSRF exposure but is not a
claim of complete protection against DNS rebinding between resolution and connection.
"""

import ipaddress
import socket
from collections.abc import Callable, Iterable
from typing import cast
from urllib.parse import urlsplit

DnsResolver = Callable[[str], Iterable[str]]


class UnsafeUrlError(ValueError):
    """A URL is outside the collector's outbound policy."""


def system_dns_resolver(host: str) -> Iterable[str]:
    return {
        cast(str, entry[4][0]) for entry in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    }


class UrlPolicy:
    def __init__(
        self, allowed_hosts: list[str], resolver: DnsResolver = system_dns_resolver
    ) -> None:
        self._allowed_hosts = set(allowed_hosts)
        self._resolver = resolver

    def validate_before_navigation(self, url: str) -> None:
        host = self._validate_shape(url)
        try:
            addresses = list(self._resolver(host))
        except (OSError, UnicodeError, ValueError) as exc:
            raise UnsafeUrlError("URL host could not be resolved") from exc
        if not addresses or any(not _is_public(address) for address in addresses):
            raise UnsafeUrlError("URL host does not resolve to public addresses")

    def validate_after_navigation(self, url: str) -> None:
        self._validate_shape(url)

    def _validate_shape(self, url: str) -> str:
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise UnsafeUrlError("URL is malformed") from exc
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            raise UnsafeUrlError("URL must use HTTP or HTTPS and include a host")
        if parsed.username is not None or parsed.password is not None:
            raise UnsafeUrlError("URL user information is not allowed")
        normalized = host.lower().rstrip(".")
        if normalized == "localhost" or normalized.endswith(".localhost"):
            raise UnsafeUrlError("localhost URLs are not allowed")
        if normalized not in self._allowed_hosts:
            raise UnsafeUrlError("URL host is not allowed")
        del port  # Access validates malformed ports.
        try:
            literal = ipaddress.ip_address(normalized)
        except ValueError:
            return normalized
        if not literal.is_global:
            raise UnsafeUrlError("non-public IP addresses are not allowed")
        return normalized


def _is_public(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False
