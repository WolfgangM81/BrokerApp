"""Config / settings tests."""

from __future__ import annotations

import pytest
from api.config import Settings


def test_dev_environment_allows_default_password() -> None:
    settings = Settings(environment="dev", postgres_password="brokerapp")
    assert settings.postgres_password == "brokerapp"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_non_dev_environment_rejects_default_password(env: str) -> None:
    with pytest.raises(ValueError, match="insecure default"):
        Settings(environment=env, postgres_password="brokerapp")


@pytest.mark.parametrize("env", ["staging", "production"])
def test_non_dev_environment_accepts_overridden_password(env: str) -> None:
    settings = Settings(environment=env, postgres_password="a-real-secret")
    assert settings.environment == env
    assert settings.postgres_password == "a-real-secret"
