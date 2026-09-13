from __future__ import annotations

import os
import unittest

from agents_calendar.config import ConfigError, load_settings


class ConfigTests(unittest.TestCase):
    def test_missing_env(self) -> None:
        old = {k: os.environ.pop(k, None) for k in ("CALDAV_URL", "CALDAV_USERNAME", "CALDAV_PASSWORD")}
        try:
            with self.assertRaises(ConfigError) as ctx:
                load_settings()
            msg = str(ctx.exception)
            self.assertIn("CALDAV_URL", msg)
            self.assertIn("CALDAV_PASSWORD", msg)
            self.assertNotIn("secret", msg)
        finally:
            for key, val in old.items():
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val

    def test_cli_missing_env(self) -> None:
        from agents_calendar.cli import main

        old = {k: os.environ.pop(k, None) for k in ("CALDAV_URL", "CALDAV_USERNAME", "CALDAV_PASSWORD")}
        try:
            self.assertEqual(main(["calendars"]), 2)
        finally:
            for key, val in old.items():
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val
