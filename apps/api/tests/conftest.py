"""Shared pytest fixtures for the API."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from api.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
