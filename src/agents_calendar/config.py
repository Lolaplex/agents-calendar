"""CalDAV and live ICS feed credentials.

Load order: <ws>/secrets.json override > <ws>/calendar.json > host
secrets.json > CALDAV_* env (host-level fallback) > legacy <ws>/.env
(one release, warns). Password never in messages."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from agents_workspace import (
        ENV_SECRETS_ORDER,
        Host,
        Workspace,
        resolve_secret,
        secrets_ws_file,
        write_secret,
    )
except ImportError:
    ENV_SECRETS_ORDER = "AGENTS_SECRETS_ORDER"
    Host = None  # type: ignore[assignment]
    Workspace = None  # type: ignore[assignment]
    resolve_secret = None  # type: ignore[assignment]
    secrets_ws_file = None  # type: ignore[assignment]
    write_secret = None  # type: ignore[assignment]


class ConfigError(ValueError):
    """Missing or invalid CalDAV credentials."""


@dataclass(frozen=True)
class Settings:
    url: str
    username: str = ""
    password: str = ""
    calendar: str = ""
    timezone: str = ""


def is_ics_feed_url(url: str) -> bool:
    raw = url.strip().lower()
    if raw.startswith("webcal://"):
        return True
    path = raw.split("?", 1)[0].split("#", 1)[0]
    return path.endswith(".ics")


def normalize_calendar_url(url: str) -> str:
    raw = url.strip()
    if raw.lower().startswith("webcal://"):
        return "https://" + raw[9:]
    return raw


def _fallback_host_dir() -> Path:
    raw = os.environ.get("AGENTS_HOST_DIR", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".agents"


def workspace_dir() -> Path:
    if Workspace is not None:
        return Workspace.from_env().dir
    return _fallback_host_dir()


def creds_path() -> Path:
    return workspace_dir() / "calendar.json"


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


def _valid_zone_name(name: str) -> str:
    raw = name.strip()
    if not raw:
        return ""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(raw)
    except Exception:
        return ""
    return raw


def _windows_timezone_name() -> str:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation",
        )
        name, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
    except Exception:
        return ""
    win_map = {
        "W. Europe Standard Time": "Europe/Berlin",
        "Central Europe Standard Time": "Europe/Warsaw",
        "Romance Standard Time": "Europe/Paris",
        "GMT Standard Time": "Europe/London",
        "Greenwich Standard Time": "UTC",
        "UTC": "UTC",
        "Eastern Standard Time": "America/New_York",
        "Central Standard Time": "America/Chicago",
        "Mountain Standard Time": "America/Denver",
        "Pacific Standard Time": "America/Los_Angeles",
    }
    return win_map.get(str(name), "")


def _os_timezone_name() -> str:
    if sys.platform == "win32":
        return _windows_timezone_name()
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        try:
            tz_path = Path("/etc/timezone")
            if tz_path.is_file():
                content = tz_path.read_text(encoding="utf-8").strip()
                if content:
                    return content
            localtime = Path("/etc/localtime")
            if localtime.is_symlink():
                target = str(localtime.resolve())
                marker = "zoneinfo/"
                if marker in target:
                    name = target.split(marker, 1)[1]
                    for prefix in ("posix/", "right/"):
                        if name.startswith(prefix):
                            name = name[len(prefix) :]
                    return name
        except Exception:
            return ""
    return ""


def detect_system_timezone() -> str:
    """Host zone from ``TZ`` or the operating system. ``UTC`` when neither is usable."""
    return system_timezone_name()


def system_timezone_name() -> str:
    """Process-local IANA zone. ``TZ`` wins, then the OS database, then ``UTC``."""
    tz_env = _valid_zone_name(os.environ.get("TZ", ""))
    if tz_env:
        return tz_env
    detected = _valid_zone_name(_os_timezone_name())
    if detected:
        return detected
    try:
        local = datetime.now().astimezone()
    except Exception:
        local = None
    if local is not None:
        key = getattr(local.tzinfo, "key", None)
        if isinstance(key, str):
            found = _valid_zone_name(key)
            if found:
                return found
        offset = local.utcoffset()
        if offset is not None and offset.total_seconds() == 0:
            return "UTC"
    return "UTC"


def configured_timezone() -> str:
    """Zone from the environment or the credentials file. Empty when unset.

    ``CALDAV_TIMEZONE`` then ``AGENTS_TIMEZONE``, then ``timezone`` in
    ``calendar.json`` or ``CALDAV_TIMEZONE`` in ``<ws>/.env``. This does
    not consult the host zone or a calendar's ``calendar-timezone`` property.
    """
    for env_var in ("CALDAV_TIMEZONE", "AGENTS_TIMEZONE"):
        val = os.environ.get(env_var, "").strip()
        if val:
            return val
    try:
        file_vals = _load_file()
    except Exception:
        return ""
    return file_vals.get("timezone", "").strip()


def get_default_timezone() -> str:
    """Configured zone, or the host zone when nothing is configured."""
    return configured_timezone() or system_timezone_name()


def _map_json(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {
        "url": str(data.get("url") or "").strip(),
        "username": str(data.get("username") or "").strip(),
        "password": str(data.get("password") or "").strip(),
        "calendar": str(data.get("calendar") or "").strip(),
        "timezone": str(data.get("timezone") or "").strip(),
    }


def _map_dotenv(data: dict[str, str]) -> dict[str, str]:
    return {
        "url": data.get("CALDAV_URL", "").strip(),
        "username": data.get("CALDAV_USERNAME", "").strip(),
        "password": data.get("CALDAV_PASSWORD", "").strip(),
        "calendar": data.get("CALDAV_CALENDAR", "").strip(),
        "timezone": data.get("CALDAV_TIMEZONE", "").strip(),
    }


def _load_secrets_file(path: Path) -> dict[str, str]:
    """CALDAV credentials from a secrets.json ``caldav`` section."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid {path}") from exc
    except OSError as exc:
        raise ConfigError(f"unreadable {path}") from exc
    section = raw.get("caldav")
    if not isinstance(section, dict):
        return {}
    return _map_json(section)


def _read_ws_vault_password(ws: object) -> str:
    if secrets_ws_file is None or ws is None:
        return ""
    path = secrets_ws_file(ws)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    val = data.get("CALDAV_PASSWORD")
    return val.strip() if isinstance(val, str) and val.strip() else ""


def _load_file() -> dict[str, str]:
    if Workspace is not None:
        ws = Workspace.from_env()
        ws_dir = ws.dir
        ws_secrets = ws.secrets
        host_secrets = Host.from_env().secrets if Host is not None else ws.host.secrets
    else:
        ws = None
        ws_dir = _fallback_host_dir()
        ws_secrets = ws_dir / "secrets.json"
        host_secrets = ws_dir / "secrets.json"
    out: dict[str, str] = {}

    def merge(src: dict[str, str]) -> None:
        for key, val in src.items():
            if val:
                out.setdefault(key, val)

    order = os.environ.get(ENV_SECRETS_ORDER, "").strip().lower()
    if order == "env-first" and resolve_secret is not None:
        vault_pw = resolve_secret("CALDAV_PASSWORD", ws=ws).strip()
        if vault_pw:
            out["password"] = vault_pw
    elif ws is not None:
        ws_vault_pw = _read_ws_vault_password(ws)
        if ws_vault_pw:
            out["password"] = ws_vault_pw

    # highest wins first; setdefault keeps earlier (higher) precedence
    if ws_secrets.is_file():
        merge(_load_secrets_file(ws_secrets))
    json_path = ws_dir / "calendar.json"
    if json_path.is_file():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid {json_path}") from exc
        except OSError as exc:
            raise ConfigError(f"unreadable {json_path}") from exc
        merge(_map_json(raw))
    if "password" not in out and resolve_secret is not None:
        env_no_pw = {k: v for k, v in os.environ.items() if k != "CALDAV_PASSWORD"}
        vault_pw = resolve_secret("CALDAV_PASSWORD", ws=ws, env=env_no_pw).strip()
        if vault_pw:
            out["password"] = vault_pw
    if host_secrets.is_file() and host_secrets != ws_secrets:
        merge(_load_secrets_file(host_secrets))
    if "password" not in out and resolve_secret is not None:
        vault_pw = resolve_secret("CALDAV_PASSWORD", ws=ws).strip()
        if vault_pw:
            out["password"] = vault_pw
    for name in ("url", "username", "password", "calendar", "timezone"):
        env_name = f"CALDAV_{name.upper()}"
        val = os.environ.get(env_name, "").strip()
        if val:
            out.setdefault(name, val)
    env_path = ws_dir / ".env"
    if env_path.is_file():
        import warnings
        warnings.warn(
            f"{env_path} is deprecated; move credentials into secrets.json",
            DeprecationWarning, stacklevel=2,
        )
        try:
            merge(_map_dotenv(_parse_dotenv(env_path.read_text(encoding="utf-8"))))
        except OSError as exc:
            raise ConfigError(f"unreadable {env_path}") from exc
    return out


def save_settings(settings: Settings, *, scope: str = "workspace") -> Path:
    """Persist non-secret settings to ``calendar.json`` and password to Host Secret Vault."""
    if scope not in ("workspace", "host"):
        raise ValueError(f"invalid secret scope: {scope!r}")
    path = creds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {}
    if settings.url.strip():
        payload["url"] = normalize_calendar_url(settings.url)
    if settings.username.strip():
        payload["username"] = settings.username.strip()
    if settings.calendar.strip():
        payload["calendar"] = settings.calendar.strip()
    if settings.timezone.strip():
        payload["timezone"] = settings.timezone.strip()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    clean_pw = settings.password.strip()
    if clean_pw:
        if write_secret is not None:
            if scope == "workspace":
                if Workspace is None:
                    raise RuntimeError("Workspace resolver unavailable")
                write_secret("CALDAV_PASSWORD", clean_pw, ws=Workspace.from_env(), scope="workspace")
            else:
                write_secret("CALDAV_PASSWORD", clean_pw, scope="host")
        else:
            import warnings

            warnings.warn(
                "agents-workspace is not installed; cannot persist CALDAV_PASSWORD "
                "to host vault (set CALDAV_PASSWORD in the environment instead)",
                UserWarning,
                stacklevel=2,
            )
    return path


def load_settings() -> Settings:
    file_vals = _load_file()
    raw_url = file_vals.get("url", "")
    url = normalize_calendar_url(raw_url)
    username = file_vals.get("username", "")
    password = file_vals.get("password", "")
    calendar = file_vals.get("calendar", "")
    timezone = configured_timezone()
    if is_ics_feed_url(raw_url):
        missing = [] if url else ["CALDAV_URL"]
    else:
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
    return Settings(
        url=url,
        username=username,
        password=password,
        calendar=calendar,
        timezone=timezone,
    )
