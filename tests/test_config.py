from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from agents_workspace import Host, doctor, resolve_secret, write_secret

from agents_calendar import config as config_mod
from agents_calendar.config import ConfigError, Settings, load_settings, save_settings


_KEYS = ("CALDAV_URL", "CALDAV_USERNAME", "CALDAV_PASSWORD", "CALDAV_CALENDAR")


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_agents = os.environ.get("AGENTS_HOST_DIR")
        os.environ["AGENTS_HOST_DIR"] = self._tmp.name
        self._old = {k: os.environ.pop(k, None) for k in _KEYS}

    def tearDown(self) -> None:
        for key, val in self._old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        if self._old_agents is None:
            os.environ.pop("AGENTS_HOST_DIR", None)
        else:
            os.environ["AGENTS_HOST_DIR"] = self._old_agents
        self._tmp.cleanup()

    def _write_json(self, **fields: str) -> Path:
        ws = Path(self._tmp.name) / "workspaces" / "default"
        ws.mkdir(parents=True, exist_ok=True)
        path = ws / "calendar.json"
        path.write_text(json.dumps(fields), encoding="utf-8")
        return path

    def test_missing_env(self) -> None:
        with self.assertRaises(ConfigError) as ctx:
            load_settings()
        msg = str(ctx.exception)
        self.assertIn("CALDAV_URL", msg)
        self.assertIn("CALDAV_PASSWORD", msg)
        self.assertIn("calendar.json", msg)
        self.assertNotIn("secret", msg)

    def test_cli_missing_env(self) -> None:
        from agents_calendar.cli import main

        self.assertEqual(main(["calendars"]), 2)

    def test_file_when_env_missing(self) -> None:
        self._write_json(url="https://dav.example/cal/", username="alice", password="file-secret")
        settings = load_settings()
        self.assertEqual(settings.url, "https://dav.example/cal/")
        self.assertEqual(settings.username, "alice")
        self.assertEqual(settings.password, "file-secret")

    def test_file_load_temp_home(self) -> None:
        os.environ.pop("AGENTS_HOST_DIR", None)
        root = Path(self._tmp.name) / "home"
        agents = root / ".agents"
        agents.mkdir(parents=True)
        ws = agents / "workspaces" / "default"
        ws.mkdir(parents=True)
        (ws / "calendar.json").write_text(
            json.dumps({"url": "https://home.example/", "username": "home-user", "password": "home-secret"}),
            encoding="utf-8",
        )
        old_home = os.environ.get("HOME")
        old_profile = os.environ.get("USERPROFILE")
        os.environ["HOME"] = str(root)
        os.environ["USERPROFILE"] = str(root)
        try:
            settings = load_settings()
            self.assertEqual(settings.url, "https://home.example/")
            self.assertEqual(settings.username, "home-user")
            self.assertEqual(settings.password, "home-secret")
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_profile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = old_profile

    def test_file_wins_over_env(self) -> None:
        # host-level env is fallback only; workspace file wins
        self._write_json(url="https://file.example/", username="file-user", password="file-secret")
        os.environ["CALDAV_URL"] = "https://env.example/"
        os.environ["CALDAV_USERNAME"] = "env-user"
        os.environ["CALDAV_PASSWORD"] = "env-secret"
        settings = load_settings()
        self.assertEqual(settings.url, "https://file.example/")
        self.assertEqual(settings.username, "file-user")
        self.assertEqual(settings.password, "file-secret")

    def test_partial_env_fills_file_gaps(self) -> None:
        self._write_json(username="file-user", password="file-secret")
        os.environ["CALDAV_URL"] = "https://env.example/"
        settings = load_settings()
        self.assertEqual(settings.url, "https://env.example/")
        self.assertEqual(settings.username, "file-user")
        self.assertEqual(settings.password, "file-secret")

    def test_dotenv_when_json_missing(self) -> None:
        env_path = Path(self._tmp.name) / "workspaces" / "default" / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            "CALDAV_URL=https://dotenv.example/\n"
            "CALDAV_USERNAME=dot-user\n"
            "CALDAV_PASSWORD=dot-secret\n",
            encoding="utf-8",
        )
        settings = load_settings()
        self.assertEqual(settings.url, "https://dotenv.example/")
        self.assertEqual(settings.username, "dot-user")
        self.assertEqual(settings.password, "dot-secret")

    def test_invalid_json_does_not_print_password(self) -> None:
        path = Path(self._tmp.name) / "workspaces" / "default" / "calendar.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not json, password=leaked-secret }", encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            load_settings()
        msg = str(ctx.exception)
        self.assertIn("invalid", msg)
        self.assertNotIn("leaked-secret", msg)

    def test_calendar_setting_from_file_and_env(self) -> None:
        self._write_json(
            url="https://dav.example/",
            username="alice",
            password="secret",
            calendar="Work",
        )
        settings = load_settings()
        self.assertEqual(settings.calendar, "Work")

        os.environ["CALDAV_CALENDAR"] = "Personal"
        settings_env = load_settings()
        self.assertEqual(settings_env.calendar, "Work")  # file wins over env fallback

    def test_timezone_config_does_not_invent_a_region(self) -> None:
        saved = {key: os.environ.pop(key, None) for key in ("CALDAV_TIMEZONE", "AGENTS_TIMEZONE", "TZ")}
        try:
            self._write_json(
                url="https://dav.example/",
                username="alice",
                password="secret",
            )
            self.assertEqual(load_settings().timezone, "")
            self._write_json(
                url="https://dav.example/",
                username="alice",
                password="secret",
                timezone="Pacific/Auckland",
            )
            self.assertEqual(load_settings().timezone, "Pacific/Auckland")
            os.environ["AGENTS_TIMEZONE"] = "America/Chicago"
            self.assertEqual(load_settings().timezone, "America/Chicago")
            os.environ["CALDAV_TIMEZONE"] = "Asia/Tokyo"
            self.assertEqual(load_settings().timezone, "Asia/Tokyo")
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_ws_secrets_overrides_calendar_json(self) -> None:
        self._write_json(url="https://file.example/", username="file-user", password="file-secret")
        import json as _json
        from pathlib import Path as _P
        (_P(self._tmp.name) / "workspaces" / "default" / "secrets.json").write_text(
            _json.dumps({"caldav": {"url": "https://wssec.example/"}}), encoding="utf-8"
        )
        settings = load_settings()
        self.assertEqual(settings.url, "https://wssec.example/")
        self.assertEqual(settings.username, "file-user")

    def test_save_settings_stores_password_in_vault_not_calendar_json(self) -> None:
        legacy_path = self._write_json(
            url="https://old.example/", username="alice", password="legacy-password"
        )
        saved_path = save_settings(
            Settings(
                url="https://dav.example/cal/",
                username="alice",
                password="vault-password",
                calendar="Work",
                timezone="Europe/Berlin",
            )
        )
        self.assertEqual(saved_path, legacy_path)
        raw = saved_path.read_text(encoding="utf-8")
        disk = json.loads(raw)
        self.assertNotIn("password", disk)
        self.assertNotIn("vault-password", raw)
        self.assertNotIn("legacy-password", raw)

        loaded = load_settings()
        self.assertEqual(loaded.url, "https://dav.example/cal/")
        self.assertEqual(loaded.username, "alice")
        self.assertEqual(loaded.password, "vault-password")
        self.assertEqual(loaded.calendar, "Work")
        self.assertEqual(loaded.timezone, "Europe/Berlin")
        self.assertEqual(doctor(Host.open(self._tmp.name))["status"], "ok")

    def test_vault_precedence_and_env_first_override(self) -> None:
        host = Host.open(self._tmp.name)
        ws = host.create("default")
        self._write_json(url="https://dav.example/", username="alice", password="legacy-pw")
        write_secret("CALDAV_PASSWORD", "ws-vault-pw", ws=ws, scope="workspace")
        os.environ["CALDAV_PASSWORD"] = "env-pw"
        self.assertEqual(load_settings().password, "ws-vault-pw")

        with patch.dict(os.environ, {"AGENTS_SECRETS_ORDER": "env-first"}):
            self.assertEqual(load_settings().password, "env-pw")

    def test_host_vault_fallback_when_calendar_json_has_no_password(self) -> None:
        host = Host.open(self._tmp.name)
        host.create("default")
        self._write_json(url="https://dav.example/", username="alice")
        write_secret("CALDAV_PASSWORD", "host-vault-pw", host=host, scope="host")
        self.assertEqual(load_settings().password, "host-vault-pw")

    def test_standalone_without_agents_workspace(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "agents_calendar_standalone_cfg_test", config_mod.__file__
        )
        assert spec is not None and spec.loader is not None
        standalone_mod = importlib.util.module_from_spec(spec)
        with patch.dict(
            sys.modules,
            {
                "agents_workspace": None,
                "agents_calendar_standalone_cfg_test": standalone_mod,
            },
        ):
            spec.loader.exec_module(standalone_mod)
        self.assertIsNone(standalone_mod.Host)
        self.assertIsNone(standalone_mod.Workspace)
        self.assertIsNone(standalone_mod.resolve_secret)
        self.assertIsNone(standalone_mod.write_secret)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            path = standalone_mod.save_settings(
                standalone_mod.Settings(
                    url="https://standalone.example/",
                    username="alice",
                    password="pw-not-written",
                )
            )
        self.assertTrue(any(issubclass(w.category, UserWarning) for w in caught))
        disk = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("password", disk)

        os.environ["CALDAV_PASSWORD"] = "env-standalone-pw"
        loaded = standalone_mod.load_settings()
        self.assertEqual(loaded.url, "https://standalone.example/")
        self.assertEqual(loaded.password, "env-standalone-pw")
