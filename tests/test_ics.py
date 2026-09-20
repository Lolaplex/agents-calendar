from __future__ import annotations

import unittest

from agents_calendar.ics import emit_vevent, parse_iso, parse_vevent, patch_vevent, to_caldav_utc


class IcsTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        raw = emit_vevent(
            uid="uid-1",
            summary="Exam; hard",
            dtstart="2026-09-14T08:00:00Z",
            dtend="2026-09-14T10:00:00Z",
            location="Uni",
            description="Line1\nLine2",
        )
        parsed = parse_vevent(raw)
        self.assertEqual(parsed["uid"], "uid-1")
        self.assertEqual(parsed["summary"], "Exam; hard")
        self.assertEqual(parsed["dtstart"], "2026-09-14T08:00:00Z")
        self.assertEqual(parsed["dtend"], "2026-09-14T10:00:00Z")
        self.assertEqual(parsed["location"], "Uni")
        self.assertEqual(parsed["description"], "Line1\nLine2")

    def test_caldav_compact(self) -> None:
        self.assertEqual(to_caldav_utc("2026-09-14T08:00:00Z"), "20260914T080000Z")
        self.assertEqual(parse_iso("20260914T080000Z").year, 2026)

    def test_date_only_all_day_utc(self) -> None:
        raw = (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:day-1\n"
            "DTSTART:20260928\nDTEND:20260929\nSUMMARY:All day\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        parsed = parse_vevent(raw)
        self.assertEqual(parsed["dtstart"], "2026-09-28T00:00:00Z")
        self.assertEqual(parsed["dtend"], "2026-09-29T00:00:00Z")
        self.assertEqual(parse_iso("20260928").day, 28)
        dated = parse_vevent(
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:day-2\n"
            "DTSTART;VALUE=DATE:20260928\nSUMMARY:Flag\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        self.assertEqual(dated["dtstart"], "2026-09-28T00:00:00Z")

    def test_patch_keeps_uid(self) -> None:
        raw = emit_vevent(
            uid="keep-me",
            summary="Old",
            dtstart="2026-09-14T08:00:00Z",
            dtend="2026-09-14T10:00:00Z",
        )
        patched = patch_vevent(raw, summary="New")
        parsed = parse_vevent(patched)
        self.assertEqual(parsed["uid"], "keep-me")
        self.assertEqual(parsed["summary"], "New")
