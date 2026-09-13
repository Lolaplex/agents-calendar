"""CalDAV credentials. Process env wins; else ~/.agents/calendar.json. Password never in messages."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Missing or invalid CalDAV credentials."""


@dataclass(frozen=True)
class Settings:
    url: str
    username: str
    password: str


def agents_home() -> Path:
    override = os.environ.get("AGENTS_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".agents"


def creds_path() -> Path:
    return agents_home() / "calendar.json"


def _parse_dotenv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def _map_json(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {
        "url": str(data.get("url") or "").strip(),
        "username": str(data.get("username") or "").strip(),
        "password": str(data.get("password") or "").strip(),
    }


def _map_dotenv(data: dict[str, str]) -> dict[str, str]:
    return {
        "url": data.get("CALDAV_URL", "").strip(),
        "username": data.get("CALDAV_USERNAME", "").strip(),
        "password": data.get("CALDAV_PASSWORD", "").strip(),
    }


def _load_file() -> dict[str, str]:
    home = agents_home()
    json_path = home / "calendar.json"
    env_path = home / ".env"
    if json_path.is_file():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid {json_path}") from exc
        except OSError as exc:
            raise ConfigError(f"unreadable {json_path}") from exc
        return _map_json(raw)
    if env_path.is_file():
        try:
            return _map_dotenv(_parse_dotenv(env_path.read_text(encoding="utf-8")))
        except OSError as exc:
            raise ConfigError(f"unreadable {env_path}") from exc
    return {}


def load_settings() -> Settings:
    file_vals = _load_file()
    url = os.environ.get("CALDAV_URL", "").strip() or file_vals.get("url", "")
    username = os.environ.get("CALDAV_USERNAME", "").strip() or file_vals.get("username", "")
    password = os.environ.get("CALDAV_PASSWORD", "").strip() or file_vals.get("password", "")
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
        raise ConfigError("Set " + ", ".join(missing) + f" or {creds_path()}")
    return Settings(url=url, username=username, password=password)
