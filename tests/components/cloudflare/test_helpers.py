"""Test Cloudflare integration helpers."""

import pytest

from homeassistant.components.cloudflare.helpers import (
    _get_type_from_ip,
    get_ip,
    get_zone_id,
)


def test_get_type_from_ip() -> None:
    """Test _get_type_from_ip."""
    assert _get_type_from_ip("") is None
    assert _get_type_from_ip("::1") == "AAAA"
    assert _get_type_from_ip("127.0.0.1") == "A"


def test_get_zone_id() -> None:
    """Test get_zone_id."""
    zones = [
        {"id": "1", "name": "example.com"},
        {"id": "2", "name": "example.org"},
    ]
    assert get_zone_id("example.com", zones) == "1"
    assert get_zone_id("example.org", zones) == "2"
    assert get_zone_id("example.net", zones) is None


@pytest.mark.parametrize(
    ("type", "content", "address", "length", "output"),
    [
        ("A", "127.0.0.1", "127.0.0.1", 64, "127.0.0.1"),
        ("A", "0.0.0.0", "127.0.0.1", 64, "127.0.0.1"),
        ("AAAA", "::1", "2001:db8::1", 128, "2001:db8::1"),
        ("AAAA", "2001:db8::1", "2002:db8::2", 64, "2002:db8::1"),
    ],
)
def test_get_ip(
    type: str, content: str, address: str, length: int, output: str
) -> None:
    """Test get_ip."""
    assert get_ip(type, content, address, length) == output
