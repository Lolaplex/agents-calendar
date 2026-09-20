from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agents_calendar.config import ConfigError, load_settings


_KEYS = ("CALDAV_URL", "CALDAV_USERNAME", "CALDAV_PASSWORD")


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_agents = os.environ.get("AGENTS_HOME")
        os.environ["AGENTS_HOME"] = self._tmp.name
        self._old = {k: os.environ.pop(k, None) for k in _KEYS}

    def tearDown(self) -> None:
        for key, val in self._old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        if self._old_agents is None:
            os.environ.pop("AGENTS_HOME", None)
        else:
            os.environ["AGENTS_HOME"] = self._old_agents
        self._tmp.cleanup()

    def _write_json(self, **fields: str) -> Path:
        path = Path(self._tmp.name) / "calendar.json"
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
        os.environ.pop("AGENTS_HOME", None)
        root = Path(self._tmp.name) / "home"
        agents = root / ".agents"
        agents.mkdir(parents=True)
        (agents / "calendar.json").write_text(
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

    def test_env_wins_over_file(self) -> None:
        self._write_json(url="https://file.example/", username="file-user", password="file-secret")
        os.environ["CALDAV_URL"] = "https://env.example/"
        os.environ["CALDAV_USERNAME"] = "env-user"
        os.environ["CALDAV_PASSWORD"] = "env-secret"
        settings = load_settings()
        self.assertEqual(settings.url, "https://env.example/")
        self.assertEqual(settings.username, "env-user")
        self.assertEqual(settings.password, "env-secret")

    def test_partial_env_overlays_file(self) -> None:
        self._write_json(url="https://file.example/", username="file-user", password="file-secret")
        os.environ["CALDAV_URL"] = "https://env.example/"
        settings = load_settings()
        self.assertEqual(settings.url, "https://env.example/")
        self.assertEqual(settings.username, "file-user")
        self.assertEqual(settings.password, "file-secret")

    def test_dotenv_when_json_missing(self) -> None:
        env_path = Path(self._tmp.name) / ".env"
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
        path = Path(self._tmp.name) / "calendar.json"
        path.write_text("{ not json, password=leaked-secret }", encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            load_settings()
        msg = str(ctx.exception)
        self.assertIn("invalid", msg)
        self.assertNotIn("leaked-secret", msg)
