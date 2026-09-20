from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents_calendar.sync import _merge_mcp_server_into_file, mcp_entry


class MergeMcpTests(unittest.TestCase):
    def test_merge_keeps_other_servers_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "mcp.json"
            config_file.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "other-server": {"command": "node", "args": ["other.js"]},
                        }
                    }
                ),
                encoding="utf-8",
            )

            res = _merge_mcp_server_into_file(config_file)
            self.assertTrue(res.startswith("OK"))

            data = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(data["mcpServers"]["other-server"], {"command": "node", "args": ["other.js"]})
            self.assertEqual(data["mcpServers"]["agents-calendar"], mcp_entry())
            self.assertEqual(data["mcpServers"]["agents-calendar"]["args"], ["-m", "agents_calendar", "serve"])

            again = _merge_mcp_server_into_file(config_file)
            self.assertTrue(again.startswith("OK"))
            updated = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(updated, data)
            self.assertEqual(updated["mcpServers"]["other-server"]["command"], "node")

    def test_merge_creates_file_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "mcp.json"
            res = _merge_mcp_server_into_file(config_file)
            self.assertTrue(res.startswith("OK"))
            data = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertIn("agents-calendar", data["mcpServers"])
            self.assertNotIn("env", data["mcpServers"]["agents-calendar"])
            self.assertNotIn("CALDAV_PASSWORD", json.dumps(data))

    def test_mcp_entry_has_no_secrets(self) -> None:
        entry = mcp_entry()
        self.assertNotIn("env", entry)
        self.assertNotIn("CALDAV_PASSWORD", json.dumps(entry))
