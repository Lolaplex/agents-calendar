from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from agents_calendar.config import get_default_timezone, system_timezone_name
from agents_calendar.ics import IcsError
from agents_calendar.tz import build_vtimezone_lines, instant_from_vtimezone, resolve_timezone


class ZoneResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = {
            key: os.environ.get(key)
            for key in ("AGENTS_HOME", "CALDAV_TIMEZONE", "AGENTS_TIMEZONE", "TZ")
        }
        os.environ["AGENTS_HOME"] = self._tmp.name
        for key in ("CALDAV_TIMEZONE", "AGENTS_TIMEZONE", "TZ"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def test_explicit_beats_config_calendar_and_system(self) -> None:
        os.environ["TZ"] = "Pacific/Auckland"
        os.environ["CALDAV_TIMEZONE"] = "Asia/Tokyo"
        zone = resolve_timezone("Europe/Berlin", calendar_tz="America/Chicago")
        self.assertEqual(zone.key, "Europe/Berlin")

    def test_config_beats_calendar_and_system(self) -> None:
        os.environ["TZ"] = "Pacific/Auckland"
        os.environ["CALDAV_TIMEZONE"] = "Asia/Tokyo"
        zone = resolve_timezone(None, calendar_tz="America/Chicago")
        self.assertEqual(zone.key, "Asia/Tokyo")
        self.assertEqual(get_default_timezone(), "Asia/Tokyo")

    def test_calendar_timezone_beats_system(self) -> None:
        os.environ["TZ"] = "Pacific/Auckland"
        zone = resolve_timezone(None, calendar_tz="America/Chicago", configured="")
        self.assertEqual(zone.key, "America/Chicago")

    def test_system_zone_then_utc(self) -> None:
        os.environ["TZ"] = "Pacific/Auckland"
        self.assertEqual(resolve_timezone(None, configured="").key, "Pacific/Auckland")
        self.assertEqual(system_timezone_name(), "Pacific/Auckland")
        os.environ["TZ"] = "Not/AZone"
        fallback = system_timezone_name()
        self.assertNotEqual(fallback, "Not/AZone")
        ZoneInfo(fallback)

    def test_unknown_zone_is_an_error(self) -> None:
        with self.assertRaises(IcsError) as caught:
            resolve_timezone("Not/AZone")
        self.assertIn("unknown timezone", str(caught.exception))


class VtimezoneOracleTests(unittest.TestCase):
    def test_component_matches_zoneinfo(self) -> None:
        samples = {
            "Europe/Berlin": (
                datetime(2026, 3, 22, 10, 0),
                datetime(2026, 3, 29, 10, 0),
                datetime(2026, 10, 18, 10, 0),
                datetime(2026, 10, 25, 10, 0),
                datetime(2026, 12, 21, 12, 0),
            ),
            "America/New_York": (
                datetime(2026, 1, 15, 10, 0),
                datetime(2026, 3, 7, 10, 0),
                datetime(2026, 3, 8, 10, 0),
                datetime(2026, 7, 15, 10, 0),
                datetime(2026, 11, 1, 10, 0),
            ),
            "Australia/Lord_Howe": (
                datetime(2026, 1, 15, 12, 0),
                datetime(2026, 7, 15, 12, 0),
            ),
            "Pacific/Auckland": (
                datetime(2026, 1, 15, 12, 0),
                datetime(2026, 7, 15, 12, 0),
            ),
            "Asia/Kolkata": (datetime(2026, 6, 1, 9, 30),),
            "UTC": (datetime(2026, 6, 1, 0, 0),),
        }
        for name, moments in samples.items():
            text = "\r\n".join(build_vtimezone_lines(name))
            self.assertIn(f"TZID:{name}", text)
            zone = ZoneInfo(name)
            for naive in moments:
                with self.subTest(zone=name, local=naive.isoformat()):
                    got = instant_from_vtimezone(text, naive, strict=True)
                    expected = naive.replace(tzinfo=zone).astimezone(timezone.utc)
                    self.assertEqual(got, expected)
        berlin = "\r\n".join(build_vtimezone_lines("Europe/Berlin"))
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", berlin)
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", berlin)
        self.assertIn("TZOFFSETFROM:+0100", berlin)
        self.assertIn("TZOFFSETTO:+0200", berlin)
        new_york = "\r\n".join(build_vtimezone_lines("America/New_York"))
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU", new_york)
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU", new_york)
        self.assertIn("TZOFFSETFROM:-0500", new_york)
        self.assertIn("TZOFFSETTO:-0400", new_york)
        kolkata = "\r\n".join(build_vtimezone_lines("Asia/Kolkata"))
        self.assertIn("TZOFFSETTO:+0530", kolkata)
