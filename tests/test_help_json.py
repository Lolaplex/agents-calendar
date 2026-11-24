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
        self.assertIn("CALDAV_CALENDAR", spec["env"])
        self.assertIn("--calendar", spec["commands"]["add"]["usage"])
        self.assertIn("--calendar", spec["commands"]["list"]["usage"])
        self.assertIn("calendar.json", spec["file"])

    def test_host_config_commands_not_exposed(self) -> None:
        # init/sync mutate host IDE MCP configs; they are CLI lifecycle, not
        # agent tools, so the cordis_expose surface must not declare them.
        spec = help_json()
        self.assertNotIn("init", spec["commands"])
        self.assertNotIn("sync", spec["commands"])
        for name, meta in spec["commands"].items():
            self.assertIn(meta["side_effects"], ("read-only", "mutating"), name)

    def test_help_json_exit(self) -> None:
        self.assertEqual(main(["--help-json"]), 0)
