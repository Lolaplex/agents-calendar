"""Minimal VEVENT emit/parse. No RRULE."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any


class IcsError(ValueError):
    """Malformed iCalendar payload."""


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _unescape_text(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt in "\\;,":
                out.append(nxt)
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(value[i])
        i += 1
    return "".join(out)


def parse_iso(value: str) -> datetime:
    raw = value.strip()
    if not raw:
        raise IcsError("empty datetime")
    compact = re.fullmatch(r"(\d{8})T(\d{6})(Z)?", raw)
    if compact:
        dt = datetime.strptime(compact.group(1) + compact.group(2), "%Y%m%d%H%M%S")
        if compact.group(3):
            return dt.replace(tzinfo=timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
    iso = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise IcsError(f"invalid datetime '{value}'") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_caldav_utc(value: str) -> str:
    return parse_iso(value).strftime("%Y%m%dT%H%M%SZ")


def to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_uid() -> str:
    return str(uuid.uuid4())


def emit_vevent(
    *,
    uid: str,
    summary: str,
    dtstart: str,
    dtend: str,
    location: str = "",
    description: str = "",
) -> str:
    start = to_caldav_utc(dtstart)
    end = to_caldav_utc(dtend)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lolaplex//agents-calendar//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{_escape_text(summary)}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape_text(location)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape_text(description)}")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(lines)


def _unfold(raw: str) -> list[str]:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _field_name(line: str) -> str:
    head = line.split(":", 1)[0]
    return head.split(";", 1)[0].upper()


def parse_vevent(raw: str) -> dict[str, Any]:
    """Parse the first VEVENT in an iCalendar payload."""
    lines = _unfold(raw)
    in_event = False
    fields: dict[str, str] = {}
    for line in lines:
        if line.upper() == "BEGIN:VEVENT":
            in_event = True
            continue
        if line.upper() == "END:VEVENT":
            break
        if not in_event or ":" not in line:
            continue
        name = _field_name(line)
        value = line.split(":", 1)[1]
        fields[name] = value
    if "UID" not in fields:
        raise IcsError("VEVENT missing UID")
    start_raw = fields.get("DTSTART", "")
    end_raw = fields.get("DTEND", "")
    event: dict[str, Any] = {
        "uid": fields["UID"],
        "summary": _unescape_text(fields.get("SUMMARY", "")),
        "dtstart": to_iso_z(parse_iso(start_raw)) if start_raw else "",
        "dtend": to_iso_z(parse_iso(end_raw)) if end_raw else "",
        "location": _unescape_text(fields.get("LOCATION", "")),
        "description": _unescape_text(fields.get("DESCRIPTION", "")),
    }
    return event


def patch_vevent(
    raw: str,
    *,
    summary: str | None = None,
    dtstart: str | None = None,
    dtend: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    parsed = parse_vevent(raw)
    return emit_vevent(
        uid=parsed["uid"],
        summary=parsed["summary"] if summary is None else summary,
        dtstart=parsed["dtstart"] if dtstart is None else dtstart,
        dtend=parsed["dtend"] if dtend is None else dtend,
        location=parsed["location"] if location is None else location,
        description=parsed["description"] if description is None else description,
    )
