"""CalDAV HTTP client. Stdlib urllib + ElementTree."""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from . import ics
from .config import Settings

DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
Transport = Callable[[str, str, bytes | None, dict[str, str]], tuple[int, dict[str, str], bytes]]


class CaldavError(RuntimeError):
    """CalDAV request failed."""


class PreconditionFailed(CaldavError):
    """HTTP 412 — missing/stale If-Match or colliding If-None-Match."""


def _tag(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def _child_text(el: ET.Element, ns: str, name: str) -> str:
    found = el.find(f".//{_tag(ns, name)}")
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _local(el: ET.Element) -> str:
    if "}" in el.tag:
        return el.tag.rsplit("}", 1)[1]
    return el.tag


class CaldavClient:
    def __init__(self, settings: Settings, transport: Transport | None = None) -> None:
        self.settings = settings
        self.base = settings.url.rstrip("/") + "/"
        self._transport = transport or self._http

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        token = base64.b64encode(
            f"{self.settings.username}:{self.settings.password}".encode("utf-8")
        ).decode("ascii")
        headers = {
            "Authorization": f"Basic {token}",
            "User-Agent": "agents-calendar/0.0.1",
        }
        if extra:
            headers.update(extra)
        return headers

    def _http(
        self, method: str, url: str, body: bytes | None, headers: dict[str, str]
    ) -> tuple[int, dict[str, str], bytes]:
        req = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                return int(resp.status), {k.lower(): v for k, v in resp.headers.items()}, resp.read()
        except HTTPError as exc:
            payload = exc.read() if exc.fp is not None else b""
            return int(exc.code), {k.lower(): v for k, v in exc.headers.items()}, payload
        except URLError as exc:
            raise CaldavError(f"CalDAV request failed: {exc.reason}") from exc

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        status, hdrs, payload = self._transport(method, url, body, self._headers(headers))
        if status == 412:
            raise PreconditionFailed("precondition failed (etag mismatch or event exists)")
        if status >= 400:
            raise CaldavError(f"CalDAV {method} {status}")
        return status, hdrs, payload

    def resolve_href(self, href: str) -> str:
        raw = href.strip()
        if not raw:
            raise CaldavError("empty href")
        parsed = urlparse(raw)
        if parsed.scheme:
            return raw
        return urljoin(self.base, raw.lstrip("/"))

    def calendars(self) -> list[dict[str, Any]]:
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<d:propfind xmlns:d="{DAV}" xmlns:c="{CALDAV}">'
            "<d:prop><d:displayname/><d:resourcetype/><d:getetag/></d:prop>"
            "</d:propfind>"
        ).encode("utf-8")
        _status, _hdrs, payload = self.request(
            "PROPFIND",
            self.base,
            body,
            {"Content-Type": "application/xml; charset=utf-8", "Depth": "1"},
        )
        rows = []
        for href, etag, node in self._responses(payload):
            rtype = node.find(f".//{_tag(DAV, 'resourcetype')}")
            is_cal = False
            if rtype is not None:
                is_cal = any(_local(child) == "calendar" for child in list(rtype))
            if not is_cal:
                continue
            rows.append(
                {
                    "href": href,
                    "etag": etag,
                    "displayname": _child_text(node, DAV, "displayname") or href,
                }
            )
        return rows

    def list_events(self, start: str, end: str) -> list[dict[str, Any]]:
        start_c = ics.to_caldav_utc(start)
        end_c = ics.to_caldav_utc(end)
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<c:calendar-query xmlns:d="{DAV}" xmlns:c="{CALDAV}">'
            "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
            "<c:filter><c:comp-filter name=\"VCALENDAR\">"
            "<c:comp-filter name=\"VEVENT\">"
            f'<c:time-range start="{start_c}" end="{end_c}"/>'
            "</c:comp-filter></c:comp-filter></c:filter>"
            "</c:calendar-query>"
        ).encode("utf-8")
        _status, _hdrs, payload = self.request(
            "REPORT",
            self.base,
            body,
            {"Content-Type": "application/xml; charset=utf-8", "Depth": "1"},
        )
        events: list[dict[str, Any]] = []
        for href, etag, node in self._responses(payload):
            data = _child_text(node, CALDAV, "calendar-data")
            if not data:
                continue
            parsed = ics.parse_vevent(data)
            parsed["href"] = href
            parsed["etag"] = etag
            events.append(parsed)
        events.sort(key=lambda row: str(row.get("dtstart") or ""))
        return events

    def add_event(
        self,
        *,
        summary: str,
        dtstart: str,
        dtend: str,
        location: str = "",
        description: str = "",
        uid: str | None = None,
    ) -> dict[str, Any]:
        event_uid = uid or ics.new_uid()
        payload = ics.emit_vevent(
            uid=event_uid,
            summary=summary,
            dtstart=dtstart,
            dtend=dtend,
            location=location,
            description=description,
        )
        href = urljoin(self.base, f"{event_uid}.ics")
        status, hdrs, _body = self.request(
            "PUT",
            href,
            payload.encode("utf-8"),
            {
                "Content-Type": "text/calendar; charset=utf-8",
                "If-None-Match": "*",
            },
        )
        if status not in (200, 201, 204):
            raise CaldavError(f"CalDAV PUT {status}")
        return {
            "href": href,
            "etag": hdrs.get("etag", ""),
            "uid": event_uid,
            "summary": summary,
            "dtstart": ics.to_iso_z(ics.parse_iso(dtstart)),
            "dtend": ics.to_iso_z(ics.parse_iso(dtend)),
            "location": location,
            "description": description,
        }

    def get_event(self, href: str) -> tuple[str, str]:
        url = self.resolve_href(href)
        _status, hdrs, payload = self.request("GET", url)
        return hdrs.get("etag", ""), payload.decode("utf-8")

    def update_event(
        self,
        href: str,
        etag: str,
        *,
        summary: str | None = None,
        dtstart: str | None = None,
        dtend: str | None = None,
        location: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        if not etag.strip():
            raise CaldavError("etag required for update")
        url = self.resolve_href(href)
        _old_etag, raw = self.get_event(href)
        patched = ics.patch_vevent(
            raw,
            summary=summary,
            dtstart=dtstart,
            dtend=dtend,
            location=location,
            description=description,
        )
        status, hdrs, _body = self.request(
            "PUT",
            url,
            patched.encode("utf-8"),
            {
                "Content-Type": "text/calendar; charset=utf-8",
                "If-Match": etag,
            },
        )
        if status not in (200, 201, 204):
            raise CaldavError(f"CalDAV PUT {status}")
        parsed = ics.parse_vevent(patched)
        parsed["href"] = href
        parsed["etag"] = hdrs.get("etag", "")
        return parsed

    def delete_event(self, href: str, etag: str) -> dict[str, str]:
        if not etag.strip():
            raise CaldavError("etag required for delete")
        url = self.resolve_href(href)
        status, _hdrs, _body = self.request(
            "DELETE",
            url,
            None,
            {"If-Match": etag},
        )
        if status not in (200, 204):
            raise CaldavError(f"CalDAV DELETE {status}")
        return {"href": href, "deleted": "true"}

    def _responses(self, payload: bytes) -> list[tuple[str, str, ET.Element]]:
        if not payload.strip():
            return []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise CaldavError("CalDAV XML parse failed") from exc
        rows: list[tuple[str, str, ET.Element]] = []
        for resp in root.iter():
            if _local(resp) != "response":
                continue
            href = _child_text(resp, DAV, "href")
            etag = _child_text(resp, DAV, "getetag")
            rows.append((href, etag, resp))
        return rows
