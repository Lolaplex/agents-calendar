from __future__ import annotations

import json
import unittest

from agents_calendar.cli import help_json, main


class HelpJsonTests(unittest.TestCase):
    def test_help_json_flag(self) -> None:
        spec = help_json()
        self.assertEqual(spec["name"], "agents-calendar")
        for name in ("list", "add", "update", "delete", "calendars", "serve"):
            self.assertIn(name, spec["commands"])
        self.assertIn("CALDAV_URL", spec["env"])

    def test_help_json_exit(self) -> None:
        self.assertEqual(main(["--help-json"]), 0)
