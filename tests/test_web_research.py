import unittest
from email.message import Message
import urllib.error

from omni.web_research import (
    GovernedWebRetriever,
    WebDocument,
    WebPolicy,
    cite,
    validate_triangulation,
)


class FakeResponse:
    def __init__(self, body, content_type="text/html; charset=utf-8"):
        self.body = body
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self, limit):
        return self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeOpener:
    def __init__(self, response):
        self.response = response

    def open(self, _request, timeout):
        self.timeout = timeout
        return self.response


class RedirectingOpener:
    def __init__(self, destination, response):
        self.destination = destination
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        if len(self.calls) == 1:
            headers = Message()
            headers["Location"] = self.destination
            raise urllib.error.HTTPError(request.full_url, 302, "Found", headers, None)
        return self.response


def public_resolver(_host, port, type):
    return [(2, type, 6, "", ("93.184.216.34", port))]


class GovernedWebTests(unittest.TestCase):
    def test_private_and_credential_urls_are_blocked(self):
        retriever = GovernedWebRetriever()
        with self.assertRaises(PermissionError):
            retriever.validate_url("http://127.0.0.1/private")
        with self.assertRaises(PermissionError):
            retriever.validate_url("https://user:password@example.com")

    def test_domain_allow_list_includes_subdomains(self):
        retriever = GovernedWebRetriever(
            WebPolicy(allowed_domains=frozenset({"example.com"}))
        )
        self.assertEqual(
            retriever.validate_url("https://docs.example.com/page"),
            "https://docs.example.com/page",
        )
        with self.assertRaises(PermissionError):
            retriever.validate_url("https://example.net/page")

    def test_fetch_extracts_text_and_provenance(self):
        response = FakeResponse(
            b"<html><head><title>Example</title><script>bad()</script></head>"
            b"<body><h1>Evidence</h1><p>Verified text.</p></body></html>"
        )
        retriever = GovernedWebRetriever(
            WebPolicy(max_response_bytes=10_000),
            resolver=public_resolver,
            opener=FakeOpener(response),
        )
        document = retriever.fetch("https://example.com/research")
        self.assertEqual(document.title, "Example")
        self.assertIn("Verified text.", document.text)
        self.assertNotIn("bad()", document.text)
        self.assertEqual(len(document.checksum), 64)

    def test_response_size_is_bounded(self):
        retriever = GovernedWebRetriever(
            WebPolicy(max_response_bytes=3),
            resolver=public_resolver,
            opener=FakeOpener(FakeResponse(b"four", "text/plain")),
        )
        with self.assertRaises(ValueError):
            retriever.fetch("https://example.com")

    def test_redirect_destination_is_revalidated_before_following(self):
        opener = RedirectingOpener(
            "https://www.example.com/final",
            FakeResponse(b"redirected evidence", "text/plain"),
        )
        retriever = GovernedWebRetriever(
            WebPolicy(max_redirects=2), resolver=public_resolver, opener=opener
        )
        document = retriever.fetch("https://example.com/start")
        self.assertEqual(document.url, "https://www.example.com/final")
        self.assertEqual(len(opener.calls), 2)

    def test_redirect_to_private_network_is_blocked(self):
        opener = RedirectingOpener(
            "http://127.0.0.1/private",
            FakeResponse(b"must not be read", "text/plain"),
        )
        retriever = GovernedWebRetriever(
            WebPolicy(max_redirects=2), resolver=public_resolver, opener=opener
        )
        with self.assertRaises(PermissionError):
            retriever.fetch("https://example.com/start")
        self.assertEqual(len(opener.calls), 1)

    def test_citations_and_triangulation(self):
        first = WebDocument(
            "https://one.example/a", "now", 200, "text/plain", "One", "a", "1", 1
        )
        second = WebDocument(
            "https://two.example/b", "now", 200, "text/plain", "Two", "b", "2", 1
        )
        citation = cite(first, "supporting evidence")
        self.assertEqual(citation.source_checksum, "1")
        validate_triangulation([first, second])
        with self.assertRaises(ValueError):
            validate_triangulation([first])


if __name__ == "__main__":
    unittest.main()
