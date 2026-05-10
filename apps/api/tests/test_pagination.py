"""Pagination cursor encoding contract."""

from __future__ import annotations

import pytest
from api.errors import APIError
from api.pagination import decode_cursor, encode_cursor


def test_encode_decode_roundtrip() -> None:
    payload = {"after_symbol": "AAPL", "n": 12}
    token = encode_cursor(payload)
    assert decode_cursor(token) == payload


def test_decode_none_returns_none() -> None:
    assert decode_cursor(None) is None


def test_decode_invalid_token_raises_api_error() -> None:
    with pytest.raises(APIError) as exc_info:
        decode_cursor("not-base64-!@#$")
    assert exc_info.value.code == "pagination.invalid_cursor"


def test_decode_non_object_token_raises_api_error() -> None:
    token = encode_cursor({"v": 1}).rstrip("=")
    # Replace the encoded JSON object with a non-object encoding:
    import base64

    bad = base64.urlsafe_b64encode(b"42").rstrip(b"=").decode()
    with pytest.raises(APIError):
        decode_cursor(bad)
    # The valid-object one still decodes fine — sanity.
    assert decode_cursor(token) == {"v": 1}
