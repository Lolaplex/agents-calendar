"""Env config. Password never appears in raised messages."""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(ValueError):
    """Missing or invalid CalDAV env."""


@dataclass(frozen=True)
class Settings:
    url: str
    username: str
    password: str


def load_settings() -> Settings:
    url = os.environ.get("CALDAV_URL", "").strip()
    username = os.environ.get("CALDAV_USERNAME", "").strip()
    password = os.environ.get("CALDAV_PASSWORD", "").strip()
    missing = [
        name
        for name, val in (
            ("CALDAV_URL", url),
            ("CALDAV_USERNAME", username),
            ("CALDAV_PASSWORD", password),
        )
        if not val
    ]
    if missing:
        raise ConfigError("Set " + ", ".join(missing))
    return Settings(url=url, username=username, password=password)
