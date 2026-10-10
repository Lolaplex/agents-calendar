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

    def test_daylight_saving_time_winter_vs_summer(self) -> None:
        # 29 Nov 2026 is CET (UTC+1, winter time)
        winter_raw = emit_vevent(
            uid="shift-winter",
            summary="Sunday shift winter",
            dtstart="2026-11-29T16:00:00",
            dtend="2026-11-29T21:00:00",
            timezone="Europe/Berlin",
        )
        parsed_winter = parse_vevent(winter_raw, tz="Europe/Berlin")
        self.assertEqual(parsed_winter["dtstart"], "2026-11-29T15:00:00Z")
        self.assertEqual(parsed_winter["dtend"], "2026-11-29T20:00:00Z")
        self.assertEqual(parsed_winter["dtstart_local"], "2026-11-29T16:00:00+01:00")
        self.assertEqual(parsed_winter["dtend_local"], "2026-11-29T21:00:00+01:00")

        # 29 Jul 2026 is CEST (UTC+2, summer time)
        summer_raw = emit_vevent(
            uid="shift-summer",
            summary="Sunday shift summer",
            dtstart="2026-07-29T16:00:00",
            dtend="2026-07-29T21:00:00",
            timezone="Europe/Berlin",
        )
        parsed_summer = parse_vevent(summer_raw, tz="Europe/Berlin")
        self.assertEqual(parsed_summer["dtstart"], "2026-07-29T14:00:00Z")
        self.assertEqual(parsed_summer["dtend"], "2026-07-29T19:00:00Z")
        self.assertEqual(parsed_summer["dtstart_local"], "2026-07-29T16:00:00+02:00")
        self.assertEqual(parsed_summer["dtend_local"], "2026-07-29T21:00:00+02:00")

    def test_parse_tzid_property(self) -> None:
        raw = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:shift-1\n"
            "DTSTART;TZID=Europe/Berlin:20261129T160000\n"
            "DTEND;TZID=Europe/Berlin:20261129T210000\n"
            "SUMMARY:Aushilfe (So)\n"
            "STATUS:CONFIRMED\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        parsed = parse_vevent(raw, tz="Europe/Berlin")
        self.assertEqual(parsed["dtstart"], "2026-11-29T15:00:00Z")
        self.assertEqual(parsed["dtend"], "2026-11-29T20:00:00Z")
        self.assertEqual(parsed["dtstart_local"], "2026-11-29T16:00:00+01:00")
        self.assertEqual(parsed["dtend_local"], "2026-11-29T21:00:00+01:00")
        self.assertEqual(parsed["status"], "CONFIRMED")
