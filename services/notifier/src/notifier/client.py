"""ntfy.sh push client.

Self-hosted ntfy is intended (e.g. `ntfy.orbiter`); HTTPS-Bearer-token auth
is supported. The function `send` is the only public entry point so
callers don't have to think about HTTP details.
"""

from __future__ import annotations

import enum
import os

import httpx
import structlog

log = structlog.get_logger("notifier")

DEFAULT_BASE = os.environ.get("NTFY_BASE_URL", "https://ntfy.orbiter")
DEFAULT_TOPIC = os.environ.get("NTFY_TOPIC", "brokerapp")
DEFAULT_TOKEN = os.environ.get("NTFY_TOKEN", "")


class NotificationLevel(enum.StrEnum):
    """ntfy priority. Maps to the `Priority` header (1=min, 5=urgent)."""

    info = "info"
    warning = "warning"
    error = "error"


_PRIORITY: dict[NotificationLevel, str] = {
    NotificationLevel.info: "3",
    NotificationLevel.warning: "4",
    NotificationLevel.error: "5",
}

_TAGS: dict[NotificationLevel, str] = {
    NotificationLevel.info: "white_check_mark",
    NotificationLevel.warning: "warning",
    NotificationLevel.error: "rotating_light",
}


class NtfyClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE,
        topic: str = DEFAULT_TOPIC,
        token: str | None = DEFAULT_TOKEN or None,
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.topic = topic
        self.token = token
        self.timeout = timeout

    def send(
        self,
        title: str,
        body: str,
        *,
        level: NotificationLevel = NotificationLevel.info,
        click_url: str | None = None,
        topic: str | None = None,
    ) -> None:
        headers = {
            "Title": title,
            "Priority": _PRIORITY[level],
            "Tags": _TAGS[level],
            "Content-Type": "text/plain; charset=utf-8",
        }
        if click_url:
            headers["Click"] = click_url
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self.base_url}/{topic or self.topic}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, content=body.encode("utf-8"), headers=headers)
            resp.raise_for_status()
            log.info("ntfy_sent", title=title, level=level.value, topic=topic or self.topic)
        except httpx.HTTPError as exc:
            log.warning("ntfy_failed", title=title, error=str(exc))


_default_client: NtfyClient | None = None


def send(
    title: str,
    body: str,
    *,
    level: NotificationLevel = NotificationLevel.info,
    click_url: str | None = None,
    topic: str | None = None,
) -> None:
    """Module-level convenience using a lazily-constructed default client."""
    global _default_client  # noqa: PLW0603  cached singleton
    if _default_client is None:
        _default_client = NtfyClient()
    _default_client.send(title, body, level=level, click_url=click_url, topic=topic)
