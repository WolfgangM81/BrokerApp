"""Cursor-based pagination.

We use opaque, base64-url cursor tokens rather than offsets because:
- Mobile / future clients need stable paging that doesn't shift when new
  rows arrive between calls.
- The token is per-endpoint and may encode whatever ordering key the
  endpoint chose.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from fastapi import Query
from pydantic import BaseModel, Field

from api.errors import bad_request

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class PageParams(BaseModel):
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    cursor: str | None = None


def page_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(None, max_length=256),
) -> PageParams:
    return PageParams(limit=limit, cursor=cursor)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(token: str | None) -> dict[str, Any] | None:
    if token is None:
        return None
    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
        result = json.loads(raw)
    except (binascii.Error, ValueError, json.JSONDecodeError) as exc:
        raise bad_request(
            code="pagination.invalid_cursor",
            detail="Pagination cursor is not a valid token.",
        ) from exc
    if not isinstance(result, dict):
        raise bad_request(
            code="pagination.invalid_cursor",
            detail="Pagination cursor must decode to an object.",
        )
    return result


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "Page",
    "PageParams",
    "decode_cursor",
    "encode_cursor",
    "page_params",
]
