from __future__ import annotations

import unittest

from agents_calendar.ics import IcsError, emit_vevent, parse_iso, parse_vevent, patch_vevent, to_caldav_utc


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

    def test_all_day_is_civil_date(self) -> None:
        raw = (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:day-1\n"
            "DTSTART:20260928\nDTEND:20260929\nSUMMARY:All day\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        parsed = parse_vevent(raw)
        self.assertTrue(parsed["all_day"])
        self.assertEqual(parsed["dtstart"], "2026-09-28")
        self.assertEqual(parsed["dtstart_local"], "2026-09-28")
        self.assertEqual(parsed["dtend"], "2026-09-29")
        self.assertEqual(parsed["dtend_local"], "2026-09-29")
        dated = parse_vevent(
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:day-2\n"
            "DTSTART;VALUE=DATE:20260928\nSUMMARY:Flag\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        self.assertTrue(dated["all_day"])
        self.assertEqual(dated["dtstart"], "2026-09-28")
        self.assertEqual(dated["dtend"], "")
        # A date-only bound is local midnight, not an all-day event and not UTC
        # unless the resolved zone is UTC.
        self.assertEqual(parse_iso("2026-09-28", default_tz="UTC").isoformat(), "2026-09-28T00:00:00+00:00")
        self.assertEqual(to_caldav_utc("2026-09-28", default_tz="Europe/Berlin"), "20260927T220000Z")

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

    def test_naive_berlin_span_is_not_utc_midnight(self) -> None:
        raw = emit_vevent(
            uid="span",
            summary="Block",
            dtstart="2026-10-22T10:00:00",
            dtend="2026-10-22T22:00:00",
            timezone="Europe/Berlin",
        )
        self.assertIn("DTSTART;TZID=Europe/Berlin:20261022T100000", raw)
        self.assertIn("DTEND;TZID=Europe/Berlin:20261022T220000", raw)
        self.assertIn("BEGIN:VTIMEZONE", raw)
        self.assertNotIn("VALUE=DATE", raw)
        parsed = parse_vevent(raw, tz="Europe/Berlin")
        self.assertFalse(parsed["all_day"])
        self.assertEqual(parsed["dtstart"], "2026-10-22T08:00:00Z")
        self.assertEqual(parsed["dtend"], "2026-10-22T20:00:00Z")
        self.assertEqual(parsed["dtstart_local"], "2026-10-22T10:00:00+02:00")
        self.assertEqual(parsed["dtend_local"], "2026-10-22T22:00:00+02:00")
        self.assertEqual(parsed["timezone"], "Europe/Berlin")

    def test_dst_boundaries_berlin_and_new_york(self) -> None:
        cases = [
            ("Europe/Berlin", "2026-03-22T10:00:00", "2026-03-22T09:00:00Z", "2026-03-22T10:00:00+01:00"),
            ("Europe/Berlin", "2026-03-29T10:00:00", "2026-03-29T08:00:00Z", "2026-03-29T10:00:00+02:00"),
            ("Europe/Berlin", "2026-10-18T10:00:00", "2026-10-18T08:00:00Z", "2026-10-18T10:00:00+02:00"),
            ("Europe/Berlin", "2026-10-25T10:00:00", "2026-10-25T09:00:00Z", "2026-10-25T10:00:00+01:00"),
            ("America/New_York", "2026-01-15T10:00:00", "2026-01-15T15:00:00Z", "2026-01-15T10:00:00-05:00"),
            ("America/New_York", "2026-03-07T10:00:00", "2026-03-07T15:00:00Z", "2026-03-07T10:00:00-05:00"),
            ("America/New_York", "2026-03-08T10:00:00", "2026-03-08T14:00:00Z", "2026-03-08T10:00:00-04:00"),
            ("America/New_York", "2026-07-15T10:00:00", "2026-07-15T14:00:00Z", "2026-07-15T10:00:00-04:00"),
            ("America/New_York", "2026-10-31T10:00:00", "2026-10-31T14:00:00Z", "2026-10-31T10:00:00-04:00"),
            ("America/New_York", "2026-11-01T10:00:00", "2026-11-01T15:00:00Z", "2026-11-01T10:00:00-05:00"),
        ]
        for zone, start, utc, local in cases:
            with self.subTest(start=start, zone=zone):
                raw = emit_vevent(
                    uid="dst",
                    summary="Wall",
                    dtstart=start,
                    dtend=start[:10] + "T11:00:00",
                    timezone=zone,
                )
                self.assertIn(f"TZID={zone}", raw)
                self.assertIn("BEGIN:VTIMEZONE", raw)
                parsed = parse_vevent(raw, tz=zone)
                self.assertEqual(parsed["dtstart"], utc)
                self.assertEqual(parsed["dtstart_local"], local)
                self.assertEqual(parsed["timezone"], zone)

    def test_weekly_wall_time_stable_across_dst(self) -> None:
        """A weekly 10:00 Europe/Berlin event stays 10:00 local across the transitions.

        The package does not expand RRULE. It stores TZID so the server's
        time-range expansion keeps that wall clock. The instants below are the
        ones that expansion produces.
        """
        master = emit_vevent(
            uid="weekly",
            summary="Standup",
            dtstart="2026-03-22T10:00:00",
            dtend="2026-03-22T10:30:00",
            timezone="Europe/Berlin",
        )
        self.assertIn("DTSTART;TZID=Europe/Berlin:20260322T100000", master)
        self.assertNotRegex(master, r"DTSTART:\d{8}T\d{6}Z")
        expected = {
            "2026-03-22": "2026-03-22T09:00:00Z",
            "2026-03-29": "2026-03-29T08:00:00Z",
            "2026-10-18": "2026-10-18T08:00:00Z",
            "2026-10-25": "2026-10-25T09:00:00Z",
        }
        for day, utc in expected.items():
            raw = (
                "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:weekly\n"
                f"DTSTART;TZID=Europe/Berlin:{day.replace('-', '')}T100000\n"
                f"DTEND;TZID=Europe/Berlin:{day.replace('-', '')}T103000\n"
                "RRULE:FREQ=WEEKLY\nSUMMARY:Standup\nEND:VEVENT\nEND:VCALENDAR\n"
            )
            parsed = parse_vevent(raw, tz="Europe/Berlin")
            self.assertEqual(parsed["dtstart"], utc)
            self.assertEqual(parsed["dtstart_local"], f"{day}T10:00:00" + parsed["dtstart_local"][19:])
            self.assertTrue(parsed["dtstart_local"].startswith(f"{day}T10:00:00"))

    def test_gap_and_ambiguous_rejected_until_offset(self) -> None:
        rejected = [
            ("Europe/Berlin", "2026-03-29T02:30:00", "2026-03-29T12:00:00", "nonexistent"),
            ("Europe/Berlin", "2026-10-25T02:30:00", "2026-10-25T12:00:00", "ambiguous"),
            ("America/New_York", "2026-03-08T02:30:00", "2026-03-08T12:00:00", "nonexistent"),
            ("America/New_York", "2026-11-01T01:30:00", "2026-11-01T12:00:00", "ambiguous"),
        ]
        for zone, start, end, needle in rejected:
            with self.subTest(start=start, zone=zone):
                with self.assertRaises(IcsError) as caught:
                    emit_vevent(uid="bad", summary="x", dtstart=start, dtend=end, timezone=zone)
                self.assertIn(needle, str(caught.exception))

        first = emit_vevent(
            uid="fold",
            summary="x",
            dtstart="2026-10-25T02:30:00+02:00",
            dtend="2026-10-25T12:00:00+01:00",
            timezone="Europe/Berlin",
        )
        parsed_first = parse_vevent(first, tz="Europe/Berlin")
        self.assertEqual(parsed_first["dtstart"], "2026-10-25T00:30:00Z")
        self.assertEqual(parsed_first["dtstart_local"], "2026-10-25T02:30:00+02:00")
        self.assertIn("DTSTART:20261025T003000Z", first)

        second = emit_vevent(
            uid="fold",
            summary="x",
            dtstart="2026-10-25T02:30:00+01:00",
            dtend="2026-10-25T12:00:00+01:00",
            timezone="Europe/Berlin",
        )
        parsed_second = parse_vevent(second, tz="Europe/Berlin")
        self.assertEqual(parsed_second["dtstart"], "2026-10-25T01:30:00Z")
        self.assertEqual(parsed_second["dtstart_local"], "2026-10-25T02:30:00+01:00")

    def test_naive_versus_explicit_offset(self) -> None:
        naive = parse_vevent(
            emit_vevent(
                uid="n",
                summary="n",
                dtstart="2026-11-29T16:00:00",
                dtend="20261129T210000",
                timezone="Europe/Berlin",
            ),
            tz="Europe/Berlin",
        )
        self.assertEqual(naive["dtstart"], "2026-11-29T15:00:00Z")
        self.assertEqual(naive["dtend"], "2026-11-29T20:00:00Z")
        spaced = parse_vevent(
            emit_vevent(
                uid="s",
                summary="s",
                dtstart="2026-11-29 16:00:00",
                dtend="2026-11-29T21:00:00",
                timezone="Europe/Berlin",
            ),
            tz="Europe/Berlin",
        )
        self.assertEqual(spaced["dtstart"], "2026-11-29T15:00:00Z")
        absolute = parse_vevent(
            emit_vevent(
                uid="z",
                summary="z",
                dtstart="2026-11-29T16:00:00Z",
                dtend="2026-11-29T20:00:00+02:00",
                timezone="Europe/Berlin",
            ),
            tz="Europe/Berlin",
        )
        self.assertEqual(absolute["dtstart"], "2026-11-29T16:00:00Z")
        self.assertEqual(absolute["dtstart_local"], "2026-11-29T17:00:00+01:00")
        self.assertEqual(absolute["dtend"], "2026-11-29T18:00:00Z")
        self.assertEqual(absolute["dtend_local"], "2026-11-29T19:00:00+01:00")

    def test_custom_tzid_uses_vtimezone(self) -> None:
        raw = (
            "BEGIN:VCALENDAR\nBEGIN:VTIMEZONE\nTZID:Custom-Berlin\n"
            "BEGIN:STANDARD\nDTSTART:19701025T030000\n"
            "TZOFFSETFROM:+0200\nTZOFFSETTO:+0100\n"
            "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\nTZNAME:CET\nEND:STANDARD\n"
            "BEGIN:DAYLIGHT\nDTSTART:19700329T020000\n"
            "TZOFFSETFROM:+0100\nTZOFFSETTO:+0200\n"
            "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\nTZNAME:CEST\nEND:DAYLIGHT\n"
            "END:VTIMEZONE\nBEGIN:VEVENT\nUID:x\n"
            "DTSTART;TZID=Custom-Berlin:20261129T160000\n"
            "DTEND;TZID=Custom-Berlin:20261129T210000\n"
            "SUMMARY:X\nEND:VEVENT\nEND:VCALENDAR\n"
        )
        parsed = parse_vevent(raw, tz="UTC")
        self.assertEqual(parsed["dtstart"], "2026-11-29T15:00:00Z")
        self.assertEqual(parsed["dtend"], "2026-11-29T20:00:00Z")
        self.assertEqual(parsed["dtstart_local"], "2026-11-29T15:00:00+00:00")
        with self.assertRaises(IcsError):
            parse_vevent(
                "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:y\n"
                "DTSTART;TZID=Not/AZone:20261129T160000\n"
                "DTEND;TZID=Not/AZone:20261129T170000\nSUMMARY:Y\n"
                "END:VEVENT\nEND:VCALENDAR\n"
            )

    def test_floating_time_uses_display_zone(self) -> None:
        raw = (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:float\n"
            "DTSTART:20261129T160000\nDTEND:20261129T170000\nSUMMARY:F\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        parsed = parse_vevent(raw, tz="Europe/Berlin")
        self.assertEqual(parsed["dtstart"], "2026-11-29T15:00:00Z")
        self.assertEqual(parsed["dtstart_local"], "2026-11-29T16:00:00+01:00")
        utc = parse_vevent(raw, tz="UTC")
        self.assertEqual(utc["dtstart"], "2026-11-29T16:00:00Z")

    def test_all_day_round_trip_exclusive_end(self) -> None:
        same = emit_vevent(
            uid="day",
            summary="One",
            dtstart="2026-11-29",
            dtend="2026-11-29",
            all_day=True,
            timezone="America/New_York",
        )
        self.assertIn("DTSTART;VALUE=DATE:20261129", same)
        self.assertIn("DTEND;VALUE=DATE:20261130", same)
        self.assertNotIn("TZID=", same)
        parsed = parse_vevent(same, tz="America/New_York")
        self.assertTrue(parsed["all_day"])
        self.assertEqual(parsed["dtstart"], "2026-11-29")
        self.assertEqual(parsed["dtend"], "2026-11-30")
        spanned = emit_vevent(
            uid="days",
            summary="Two",
            dtstart="2026-11-29",
            dtend="2026-12-01",
            timezone="UTC",
        )
        self.assertIn("DTEND;VALUE=DATE:20261201", spanned)

    def test_patch_preserves_rrule_alarm_and_bumps_sequence(self) -> None:
        raw = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VTIMEZONE\r\nTZID:Europe/Berlin\r\n"
            "BEGIN:STANDARD\r\nDTSTART:19701025T030000\r\nTZOFFSETFROM:+0200\r\n"
            "TZOFFSETTO:+0100\r\nRRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\r\n"
            "TZNAME:CET\r\nEND:STANDARD\r\nBEGIN:DAYLIGHT\r\nDTSTART:19700329T020000\r\n"
            "TZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\n"
            "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\nTZNAME:CEST\r\nEND:DAYLIGHT\r\n"
            "END:VTIMEZONE\r\nBEGIN:VEVENT\r\nUID:keep-uid\r\nSEQUENCE:4\r\n"
            "DTSTAMP:20200101T000000Z\r\n"
            "DTSTART;TZID=Europe/Berlin:20260322T100000\r\n"
            "DTEND;TZID=Europe/Berlin:20260322T120000\r\n"
            "RRULE:FREQ=WEEKLY;BYDAY=SU\r\n"
            "EXDATE;TZID=Europe/Berlin:20260405T100000\r\n"
            "SUMMARY:Old\r\nATTENDEE;CN=Ada:mailto:ada@example.com\r\n"
            "X-CUSTOM:keep-me\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\n"
            "DESCRIPTION:Wake up\r\nTRIGGER:-PT15M\r\nEND:VALARM\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        patched = patch_vevent(raw, summary="New")
        for needle in (
            "UID:keep-uid",
            "SUMMARY:New",
            "RRULE:FREQ=WEEKLY;BYDAY=SU",
            "EXDATE;TZID=Europe/Berlin:20260405T100000",
            "ATTENDEE;CN=Ada:mailto:ada@example.com",
            "X-CUSTOM:keep-me",
            "BEGIN:VALARM",
            "DESCRIPTION:Wake up",
            "TRIGGER:-PT15M",
            "SEQUENCE:5",
            "DTSTART;TZID=Europe/Berlin:20260322T100000",
            "LAST-MODIFIED:",
            "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        ):
            self.assertIn(needle, patched)
        self.assertNotIn("SUMMARY:Old", patched)
        self.assertNotIn("DTSTAMP:20200101T000000Z", patched)
        self.assertEqual(patched.count("BEGIN:VTIMEZONE"), 1)
        moved = patch_vevent(patched, dtstart="2026-03-29T10:00:00", timezone="Europe/Berlin")
        self.assertIn("DTSTART;TZID=Europe/Berlin:20260329T100000", moved)
        self.assertIn("RRULE:FREQ=WEEKLY;BYDAY=SU", moved)
        self.assertIn("BEGIN:VALARM", moved)
        self.assertIn("SEQUENCE:6", moved)
        parsed = parse_vevent(moved, tz="Europe/Berlin")
        self.assertEqual(parsed["summary"], "New")
        self.assertEqual(parsed["dtstart"], "2026-03-29T08:00:00Z")
        self.assertEqual(parsed["dtend"], "2026-03-29T10:00:00Z")
