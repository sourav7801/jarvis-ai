"""Governed HTTP research retrieval with SSRF controls and provenance."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable


ALLOWED_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
)


@dataclass(frozen=True)
class WebPolicy:
    allowed_domains: frozenset[str] = frozenset()
    blocked_domains: frozenset[str] = frozenset()
    max_response_bytes: int = 2_000_000
    timeout_seconds: float = 20.0
    user_agent: str = "OMNI-JARVIS-Research/0.1"
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if self.max_response_bytes < 1 or self.max_response_bytes > 20_000_000:
            raise ValueError("Response limit must be between 1 byte and 20 MB.")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise ValueError("HTTP timeout must be in the range (0, 120].")
        if self.max_redirects < 0 or self.max_redirects > 10:
            raise ValueError("Redirect limit must be between 0 and 10.")


@dataclass(frozen=True)
class WebDocument:
    url: str
    retrieved_at: str
    status: int
    content_type: str
    title: str
    text: str
    checksum: str
    byte_count: int


@dataclass(frozen=True)
class Citation:
    title: str
    url: str
    retrieved_at: str
    source_checksum: str
    excerpt: str


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored = 0
        self._title = False

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored += 1
        if tag == "title":
            self._title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._ignored:
            self._ignored -= 1
        if tag == "title":
            self._title = False

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value or self._ignored:
            return
        if self._title:
            self.title_parts.append(value)
        self.parts.append(value)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class GovernedWebRetriever:
    def __init__(
        self,
        policy: WebPolicy | None = None,
        resolver: Callable = socket.getaddrinfo,
        opener=None,
    ):
        self.policy = policy or WebPolicy()
        self.resolver = resolver
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    @staticmethod
    def _domain_matches(host: str, domain: str) -> bool:
        domain = domain.lower().lstrip(".")
        return host == domain or host.endswith("." + domain)

    def validate_url(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(str(url).strip())
        if parsed.scheme.lower() not in {"http", "https"}:
            raise PermissionError("Only HTTP and HTTPS URLs are allowed.")
        if parsed.username or parsed.password:
            raise PermissionError("Credentials in URLs are not allowed.")
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            raise ValueError("URL hostname is required.")
        if any(self._domain_matches(host, item) for item in self.policy.blocked_domains):
            raise PermissionError("URL domain is blocked by policy.")
        if self.policy.allowed_domains and not any(
            self._domain_matches(host, item) for item in self.policy.allowed_domains
        ):
            raise PermissionError("URL domain is outside the allow-list.")
        try:
            literal = ipaddress.ip_address(host.strip("[]"))
            self._reject_address(literal)
        except ValueError:
            pass
        return urllib.parse.urlunsplit(parsed)

    @staticmethod
    def _reject_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        if any(
            (
                address.is_private,
                address.is_loopback,
                address.is_link_local,
                address.is_multicast,
                address.is_reserved,
                address.is_unspecified,
            )
        ):
            raise PermissionError("Private or special network addresses are blocked.")

    def _resolve_public(self, host: str, port: int) -> None:
        addresses = self.resolver(host, port, type=socket.SOCK_STREAM)
        if not addresses:
            raise ConnectionError("Hostname did not resolve.")
        for item in addresses:
            self._reject_address(ipaddress.ip_address(item[4][0]))

    def fetch(self, url: str) -> WebDocument:
        normalized = self.validate_url(url)
        response = None
        for redirect_count in range(self.policy.max_redirects + 1):
            parsed = urllib.parse.urlsplit(normalized)
            self._resolve_public(
                parsed.hostname or "",
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
            request = urllib.request.Request(
                normalized,
                headers={
                    "User-Agent": self.policy.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/json,application/xml,text/plain",
                },
                method="GET",
            )
            try:
                response = self.opener.open(
                    request, timeout=self.policy.timeout_seconds
                )
                break
            except urllib.error.HTTPError as error:
                if not 300 <= error.code < 400:
                    raise
                location = error.headers.get("Location") if error.headers else None
                if not location:
                    raise PermissionError("Redirect response did not include a destination.") from error
                if redirect_count >= self.policy.max_redirects:
                    raise PermissionError("Redirect limit exceeded.") from error
                normalized = self.validate_url(
                    urllib.parse.urljoin(normalized, location)
                )
        if response is None:
            raise ConnectionError("Web response was unavailable.")
        parsed = urllib.parse.urlsplit(normalized)
        with response:
            content_type = response.headers.get_content_type().lower()
            if not any(content_type.startswith(item) for item in ALLOWED_CONTENT_TYPES):
                raise ValueError(f"Unsupported content type: {content_type}")
            raw = response.read(self.policy.max_response_bytes + 1)
            if len(raw) > self.policy.max_response_bytes:
                raise ValueError("Response exceeded the configured byte limit.")
            charset = response.headers.get_content_charset() or "utf-8"
            decoded = raw.decode(charset, errors="replace")
            status = int(getattr(response, "status", 200))

        title = ""
        text = decoded
        if content_type in {"text/html", "application/xhtml+xml"}:
            parser = _TextExtractor()
            parser.feed(decoded)
            title = " ".join(parser.title_parts).strip()
            text = "\n".join(parser.parts)
        checksum = hashlib.sha256(raw).hexdigest()
        return WebDocument(
            normalized,
            datetime.now(timezone.utc).isoformat(),
            status,
            content_type,
            title or parsed.hostname or normalized,
            text,
            checksum,
            len(raw),
        )


def cite(document: WebDocument, excerpt: str) -> Citation:
    value = " ".join(str(excerpt).split()).strip()
    if not value:
        raise ValueError("Citation excerpt cannot be empty.")
    if len(value) > 500:
        value = value[:500]
    return Citation(
        document.title,
        document.url,
        document.retrieved_at,
        document.checksum,
        value,
    )


def validate_triangulation(documents: list[WebDocument], minimum_sources: int = 2) -> None:
    if minimum_sources < 1:
        raise ValueError("minimum_sources must be positive.")
    domains = {
        (urllib.parse.urlsplit(document.url).hostname or "").lower()
        for document in documents
    }
    if len(domains) < minimum_sources:
        raise ValueError(
            f"Research requires at least {minimum_sources} distinct source domains."
        )
