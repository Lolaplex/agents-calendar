from __future__ import annotations

from pathlib import Path
import unittest

from agents_calendar.client import CaldavClient, CaldavError, PreconditionFailed
from agents_calendar.config import Settings

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _settings() -> Settings:
    return Settings(
        url="https://cal.example/calendars/user/default/",
        username="user",
        password="secret",
    )


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes | None, dict[str, str]]] = []
        self.handlers: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.store: dict[str, tuple[str, bytes]] = {}

    def add(self, method: str, url_suffix: str, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.handlers[f"{method} {url_suffix}"] = (status, headers or {}, body)

    def __call__(
        self, method: str, url: str, body: bytes | None, headers: dict[str, str]
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append((method, url, body, headers))
        if method == "PUT" and headers.get("If-None-Match") == "*":
            if url in self.store:
                return 412, {}, b""
            etag = '"new-etag"'
            self.store[url] = (etag, body or b"")
            return 201, {"etag": etag}, b""
        if method == "PUT" and "If-Match" in headers:
            expected = headers["If-Match"]
            current = self.store.get(url)
            if current is None or current[0] != expected:
                return 412, {}, b""
            etag = '"upd-etag"'
            self.store[url] = (etag, body or b"")
            return 204, {"etag": etag}, b""
        if method == "GET":
            row = self.store.get(url)
            if row is None:
                return 404, {}, b""
            return 200, {"etag": row[0]}, row[1]
        if method == "DELETE":
            expected = headers.get("If-Match", "")
            current = self.store.get(url)
            if current is None or current[0] != expected:
                return 412, {}, b""
            del self.store[url]
            return 204, {}, b""
        for key, resp in self.handlers.items():
            m, suffix = key.split(" ", 1)
            if m == method and url.endswith(suffix):
                return resp
        return 500, {}, b"unhandled"


class ClientTests(unittest.TestCase):
    def test_list_parses_fixture(self) -> None:
        transport = FakeTransport()
        transport.add("REPORT", "/calendars/user/default/", 207, (FIXTURES / "report.xml").read_bytes())
        client = CaldavClient(_settings(), transport=transport)
        rows = client.list_events("2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["summary"], "Exam")
        self.assertEqual(rows[0]["etag"], '"etag-1"')
        self.assertIn("exam.ics", rows[0]["href"])
        method, _url, body, _hdrs = transport.calls[0]
        self.assertEqual(method, "REPORT")
        self.assertIn(b"20260913T000000Z", body or b"")

    def test_calendars_skips_non_calendar(self) -> None:
        transport = FakeTransport()
        transport.add("PROPFIND", "/calendars/user/default/", 207, (FIXTURES / "propfind.xml").read_bytes())
        client = CaldavClient(_settings(), transport=transport)
        rows = client.calendars()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["displayname"], "Personal")

    def test_add_if_none_match(self) -> None:
        transport = FakeTransport()
        client = CaldavClient(_settings(), transport=transport)
        row = client.add_event(
            summary="Exam",
            dtstart="2026-09-14T08:00:00Z",
            dtend="2026-09-14T10:00:00Z",
            uid="fixed-uid",
        )
        self.assertEqual(row["uid"], "fixed-uid")
        self.assertEqual(transport.calls[0][3].get("If-None-Match"), "*")
        with self.assertRaises(PreconditionFailed):
            client.add_event(
                summary="Exam",
                dtstart="2026-09-14T08:00:00Z",
                dtend="2026-09-14T10:00:00Z",
                uid="fixed-uid",
            )

    def test_update_requires_etag(self) -> None:
        client = CaldavClient(_settings(), transport=FakeTransport())
        with self.assertRaises(CaldavError):
            client.update_event("/x.ics", "", summary="Nope")

    def test_update_and_delete_if_match(self) -> None:
        transport = FakeTransport()
        client = CaldavClient(_settings(), transport=transport)
        created = client.add_event(
            summary="Exam",
            dtstart="2026-09-14T08:00:00Z",
            dtend="2026-09-14T10:00:00Z",
            uid="upd-uid",
        )
        updated = client.update_event(created["href"], created["etag"], summary="Exam 2")
        self.assertEqual(updated["summary"], "Exam 2")
        with self.assertRaises(PreconditionFailed):
            client.delete_event(created["href"], created["etag"])
        gone = client.delete_event(created["href"], updated["etag"])
        self.assertEqual(gone["deleted"], "true")

    def test_password_not_in_payload(self) -> None:
        transport = FakeTransport()
        transport.add("REPORT", "/calendars/user/default/", 207, (FIXTURES / "report.xml").read_bytes())
        client = CaldavClient(_settings(), transport=transport)
        client.list_events("2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z")
        _method, _url, body, headers = transport.calls[0]
        self.assertNotIn(b"secret", body or b"")
        self.assertIn("Basic ", headers.get("Authorization", ""))

    def test_principal_home_report(self) -> None:
        wellknown = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:response><d:href>/.well-known/caldav</d:href><d:propstat><d:prop>"
            "<d:current-user-principal><d:href>/123/principal/</d:href></d:current-user-principal>"
            "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            "</d:multistatus>"
        ).encode("utf-8")
        principal = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:response><d:href>/123/principal/</d:href><d:propstat><d:prop>"
            "<c:calendar-home-set><d:href>/123/calendars/</d:href></c:calendar-home-set>"
            "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            "</d:multistatus>"
        ).encode("utf-8")
        home = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:response><d:href>/123/calendars/work/</d:href><d:propstat><d:prop>"
            "<d:displayname>Work</d:displayname><d:getetag>\"cal-w\"</d:getetag>"
            "<d:resourcetype><d:collection/><c:calendar/></d:resourcetype>"
            "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            "</d:multistatus>"
        ).encode("utf-8")
        transport = FakeTransport()
        transport.add("REPORT", "https://caldav.icloud.com/", 403, b"")
        transport.add("PROPFIND", "https://caldav.icloud.com/", 400, b"")
        transport.add("PROPFIND", ".well-known/caldav", 207, wellknown)
        transport.add("PROPFIND", "/123/principal/", 207, principal)
        transport.add("PROPFIND", "/123/calendars/", 207, home)
        transport.add("REPORT", "/123/calendars/work/", 207, (FIXTURES / "report.xml").read_bytes())
        client = CaldavClient(
            Settings(url="https://caldav.icloud.com", username="user", password="secret"),
            transport=transport,
        )
        rows = client.list_events("2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["summary"], "Exam")
        methods = [call[0] for call in transport.calls]
        self.assertEqual(methods[0], "REPORT")
        self.assertIn("PROPFIND", methods)
        self.assertGreaterEqual(methods.count("REPORT"), 2)


if __name__ == "__main__":
    unittest.main()
