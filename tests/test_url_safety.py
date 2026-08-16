import socket
from unittest.mock import patch

import pytest

from recipe_extractor.url_safety import UnsafeUrlError, normalize_url, resolve_safe_target


def test_normalize_url_removes_fragment_and_default_port():
    assert normalize_url("HTTPS://Example.COM:443/a?b=1#frag") == "https://example.com/a?b=1"


def test_normalize_url_rejects_credentials():
    with pytest.raises(UnsafeUrlError):
        normalize_url("https://user:pass@example.com/recipe")


def test_normalize_url_rejects_non_web_scheme():
    with pytest.raises(UnsafeUrlError):
        normalize_url("file:///etc/passwd")


def test_normalize_url_rejects_nonstandard_port():
    with pytest.raises(UnsafeUrlError):
        normalize_url("https://example.com:8443/recipe")


def test_resolution_rejects_any_private_address():
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ]
    with patch("socket.getaddrinfo", return_value=answers), pytest.raises(UnsafeUrlError):
        resolve_safe_target("https://example.com/recipe")


def test_resolution_returns_pinned_public_addresses():
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=answers):
        target = resolve_safe_target("https://example.com/recipe")
    assert target.addresses == ("93.184.216.34",)
    assert target.hostname == "example.com"
    assert target.request_target == "/recipe"
