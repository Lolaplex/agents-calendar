"""iCalendar read/write. Timed values use IANA zones; all-day values are dates."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo

from .tz import (
    IcsError,
    build_vtimezone_lines,
    format_date,
    format_local,
    format_utc,
    format_zoned_line,
    interpret_zoned_value,
    is_date_only,
    localize_wall,
    parse_user_time,
    resolve_timezone,
    to_caldav_utc as _to_caldav_utc,
    vtimezone_map,
    zone_key,
)

__all__ = [
    "IcsError",
    "emit_vevent",
    "is_date_only",
    "new_uid",
    "parse_iso",
    "parse_vevent",
    "patch_vevent",
    "resolve_timezone",
    "to_caldav_utc",
    "to_iso_local",
    "to_iso_z",
]

_UTC = dt_timezone.utc


def to_caldav_utc(value: str, default_tz: str | ZoneInfo | None = None) -> str:
    zone = resolve_timezone(default_tz)
    return _to_caldav_utc(value, zone)


def parse_iso(value: str, default_tz: str | ZoneInfo | None = None) -> datetime:
    """UTC instant. A date-only value is local midnight in the resolved zone."""
    parsed = parse_user_time(value, resolve_timezone(default_tz))
    if parsed.all_day and parsed.civil is not None:
        midnight = datetime(parsed.civil.year, parsed.civil.month, parsed.civil.day)
        return localize_wall(midnight, parsed.zone, strict=True).astimezone(_UTC)
    if parsed.instant is None:
        raise IcsError(f"invalid datetime '{value}'")
    return parsed.instant


def to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return format_utc(dt)


def to_iso_local(dt: datetime, default_tz: str | ZoneInfo | None = None) -> str:
    zone = resolve_timezone(default_tz)
    if dt.tzinfo is None:
        dt = localize_wall(dt, zone, strict=True)
    return format_local(dt, zone)


def new_uid() -> str:
    return str(uuid.uuid4())


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
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append("\n" if nxt == "n" else nxt)
            index += 2
            continue
        out.append(value[index])
        index += 1
    return "".join(out)


def _fold_line(line: str) -> list[str]:
    data = line.encode("utf-8")
    if len(data) <= 75:
        return [line]
    chunks: list[bytes] = []
    limit = 75
    while len(data) > limit:
        cut = limit
        while cut > 0 and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        if cut <= 0:
            cut = limit
        chunks.append(data[:cut])
        data = data[cut:]
        limit = 74
    chunks.append(data)
    return [chunks[0].decode("utf-8")] + [" " + chunk.decode("utf-8") for chunk in chunks[1:]]


def _fold(lines: list[str]) -> str:
    folded: list[str] = []
    for line in lines:
        folded.extend(_fold_line(line))
    folded.append("")
    return "\r\n".join(folded)


def _unfold(raw: str) -> list[str]:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        elif line != "":
            lines.append(line)
    return lines


def _parse_line(line: str) -> tuple[str, dict[str, str], str]:
    colon = line.find(":")
    if colon < 0:
        return "", {}, ""
    head = line[:colon]
    value = line[colon + 1 :]
    parts = head.split(";")
    name = parts[0].strip().upper()
    params: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        params[key.strip().upper()] = val.strip().strip("'\"")
    return name, params, value


def _stamp(moment: datetime | None = None) -> str:
    current = moment or datetime.now(_UTC)
    return current.astimezone(_UTC).strftime("%Y%m%dT%H%M%SZ")


def _require_span(start: datetime, end: datetime) -> None:
    if end <= start:
        raise IcsError("dtend must be after dtstart")


def _require_dates(start: date, end: date) -> None:
    if end <= start:
        raise IcsError("all-day DTEND must be after DTSTART (DTEND is exclusive)")


def _exclusive_end(start: date, end: date | None) -> date:
    if end is None or end == start:
        return start + timedelta(days=1)
    _require_dates(start, end)
    return end


def _civil_from_user(value: str, zone: ZoneInfo) -> date:
    parsed = parse_user_time(value, zone)
    if parsed.all_day and parsed.civil is not None:
        return parsed.civil
    if parsed.instant is None:
        raise IcsError(f"invalid date '{value}'")
    return parsed.instant.astimezone(zone).date()


def _timed_lines(start: datetime, end: datetime, zone: ZoneInfo) -> tuple[list[str], bool]:
    _require_span(start, end)
    start_line, start_tzid = format_zoned_line("DTSTART", start, zone)
    end_line, end_tzid = format_zoned_line("DTEND", end, zone)
    return [start_line, end_line], start_tzid or end_tzid


def emit_vevent(
    *,
    uid: str,
    summary: str,
    dtstart: str,
    dtend: str,
    location: str = "",
    description: str = "",
    timezone: str | None = None,
    all_day: bool = False,
    status: str = "",
) -> str:
    zone = resolve_timezone(timezone)
    date_start = is_date_only(dtstart)
    date_end = (not dtend) or is_date_only(dtend)
    if all_day or (date_start and date_end):
        use_all_day = True
    elif date_start or (bool(dtend) and is_date_only(dtend)):
        raise IcsError("timed events need a date-time for both dtstart and dtend")
    else:
        use_all_day = False
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lolaplex//agents-calendar//EN",
        "CALSCALE:GREGORIAN",
    ]
    if use_all_day:
        start_day = _civil_from_user(dtstart, zone)
        end_day = _exclusive_end(start_day, _civil_from_user(dtend, zone) if dtend else None)
        start_line = f"DTSTART;VALUE=DATE:{start_day.strftime('%Y%m%d')}"
        end_line = f"DTEND;VALUE=DATE:{end_day.strftime('%Y%m%d')}"
        body = [start_line, end_line]
    else:
        if is_date_only(dtstart) or is_date_only(dtend):
            raise IcsError("timed events need a date-time for both dtstart and dtend")
        start = parse_user_time(dtstart, zone)
        end = parse_user_time(dtend, zone)
        if start.instant is None or end.instant is None:
            raise IcsError("timed events need a date-time for both dtstart and dtend")
        body, needs_zone = _timed_lines(start.instant, end.instant, zone)
        if needs_zone:
            lines.extend(build_vtimezone_lines(zone_key(zone)))
    lines.extend(
        [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_stamp()}",
            *body,
            f"SUMMARY:{_escape_text(summary)}",
        ]
    )
    if location:
        lines.append(f"LOCATION:{_escape_text(location)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape_text(description)}")
    if status:
        lines.append(f"STATUS:{status.strip().upper()}")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return _fold(lines)


def _value_is_date(params: dict[str, str], value: str) -> bool:
    if params.get("VALUE", "").upper() == "DATE":
        return True
    return bool(value) and is_date_only(value) and "T" not in value.upper()


def _as_date(value: str) -> date:
    raw = value.strip()
    if re.fullmatch(r"\d{8}", raw):
        return datetime.strptime(raw, "%Y%m%d").date()
    return date.fromisoformat(raw)


def _has_explicit_offset(value: str) -> bool:
    raw = value.strip()
    if raw.upper().endswith("Z"):
        return True
    return bool(re.search(r"[+-]\d{2}:?\d{2}$", raw))


def _event_instant(
    params: dict[str, str],
    value: str,
    *,
    display: ZoneInfo,
    vtimezones: dict[str, str],
    strict: bool,
) -> datetime:
    raw = value.strip()
    if params.get("TZID") and not _has_explicit_offset(raw):
        return interpret_zoned_value(
            raw,
            tzid=params["TZID"],
            vtimezones=vtimezones,
            strict=strict,
        )
    if _has_explicit_offset(raw):
        return parse_iso(raw, display)
    return localize_wall(_naive_wall(raw), display, strict=strict).astimezone(_UTC)


def _naive_wall(value: str) -> datetime:
    raw = value.strip()
    upper = raw.upper()
    if re.fullmatch(r"\d{8}T\d{6}", upper):
        return datetime.strptime(upper, "%Y%m%dT%H%M%S")
    text = raw.replace(" ", "T", 1) if " " in raw[:11] else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise IcsError(f"invalid datetime '{value}'") from exc
    if parsed.tzinfo is not None:
        raise IcsError(f"expected a floating date-time, got '{value}'")
    return parsed


def parse_vevent(raw: str, tz: str | ZoneInfo | None = None) -> dict[str, Any]:
    """Parse the first VEVENT.

    ``dtstart`` / ``dtend`` are UTC instants, or ``YYYY-MM-DD`` when ``all_day``
    is true (``DTEND`` is exclusive). ``dtstart_local`` / ``dtend_local`` use
    the display zone and include a numeric offset. Floating values use that
    same zone; ``TZID`` uses the IANA database, or the embedded ``VTIMEZONE``
    when the id is not an IANA name.
    """
    lines = _unfold(raw)
    vtimezones = vtimezone_map(raw)
    in_event = False
    depth = 0
    fields: dict[str, tuple[dict[str, str], str]] = {}
    for line in lines:
        upper = line.strip().upper()
        if upper.startswith("BEGIN:"):
            depth += 1
            if upper == "BEGIN:VEVENT" and not in_event:
                in_event = True
                depth = 1
            continue
        if upper.startswith("END:"):
            if in_event and upper == "END:VEVENT" and depth == 1:
                break
            depth = max(0, depth - 1)
            continue
        if not in_event or depth != 1 or ":" not in line:
            continue
        name, params, value = _parse_line(line)
        if name and name not in fields:
            fields[name] = (params, value)

    if "UID" not in fields:
        raise IcsError("VEVENT missing UID")

    display = resolve_timezone(tz)
    start_params, start_raw = fields.get("DTSTART", ({}, ""))
    end_params, end_raw = fields.get("DTEND", ({}, ""))
    all_day = _value_is_date(start_params, start_raw) or _value_is_date(end_params, end_raw)
    if all_day and start_raw and not _value_is_date(start_params, start_raw):
        raise IcsError("VEVENT mixes VALUE=DATE with a date-time")

    event: dict[str, Any] = {
        "uid": fields["UID"][1].strip(),
        "summary": _unescape_text(fields.get("SUMMARY", ({}, ""))[1]),
        "dtstart": "",
        "dtstart_local": "",
        "dtend": "",
        "dtend_local": "",
        "timezone": zone_key(display),
        "all_day": all_day,
        "location": _unescape_text(fields.get("LOCATION", ({}, ""))[1]),
        "description": _unescape_text(fields.get("DESCRIPTION", ({}, ""))[1]),
    }
    status_raw = fields.get("STATUS", ({}, ""))[1]
    if status_raw:
        event["status"] = status_raw.strip().upper()

    if all_day:
        if start_raw:
            start_day = format_date(_as_date(start_raw))
            event["dtstart"] = start_day
            event["dtstart_local"] = start_day
        if end_raw:
            end_day = format_date(_as_date(end_raw))
            event["dtend"] = end_day
            event["dtend_local"] = end_day
        return event

    if start_raw:
        start = _event_instant(start_params, start_raw, display=display, vtimezones=vtimezones, strict=False)
        event["dtstart"] = format_utc(start)
        event["dtstart_local"] = format_local(start, display)
    if end_raw:
        end = _event_instant(end_params, end_raw, display=display, vtimezones=vtimezones, strict=False)
        event["dtend"] = format_utc(end)
        event["dtend_local"] = format_local(end, display)
    return event


def _parsed_instant(parsed: dict[str, Any], utc_key: str, local_key: str) -> datetime:
    local = str(parsed.get(local_key) or "")
    utc = str(parsed.get(utc_key) or "")
    source = local if local and ("+" in local[10:] or local.endswith("Z")) else utc
    if not source:
        raise IcsError(f"existing event has no {utc_key}")
    return parse_iso(source, "UTC")


def _parsed_date(parsed: dict[str, Any], key: str) -> date:
    raw = str(parsed.get(key) or "")
    if not raw:
        raise IcsError(f"existing all-day event has no {key}")
    return date.fromisoformat(raw[:10])


def _replacement_times(
    parsed: dict[str, Any],
    *,
    dtstart: str | None,
    dtend: str | None,
    all_day: bool | None,
    zone: ZoneInfo,
) -> tuple[list[str], bool]:
    previous_all_day = bool(parsed.get("all_day"))
    if all_day is None:
        if dtstart is None and dtend is None:
            use_all_day = previous_all_day
        elif (dtstart is None or is_date_only(dtstart)) and (dtend is None or is_date_only(dtend)):
            use_all_day = previous_all_day or is_date_only(dtstart or "") or is_date_only(dtend or "")
            if dtstart and not is_date_only(dtstart):
                use_all_day = False
            if dtend and not is_date_only(dtend):
                use_all_day = False
        else:
            use_all_day = False
    else:
        use_all_day = all_day

    if use_all_day:
        if dtstart is not None:
            start_day = _civil_from_user(dtstart, zone)
        elif previous_all_day:
            start_day = _parsed_date(parsed, "dtstart")
        elif parsed.get("dtstart"):
            start_day = _parsed_instant(parsed, "dtstart", "dtstart_local").astimezone(zone).date()
        else:
            raise IcsError("all-day update needs dtstart")
        if dtend is not None:
            end_day = _exclusive_end(start_day, _civil_from_user(dtend, zone))
        elif previous_all_day and parsed.get("dtend"):
            end_day = _parsed_date(parsed, "dtend")
            old_start_day = _parsed_date(parsed, "dtstart")
            if end_day <= start_day:
                span = end_day - old_start_day
                if span <= timedelta(0):
                    span = timedelta(days=1)
                end_day = start_day + span
        elif parsed.get("dtend"):
            end_instant = _parsed_instant(parsed, "dtend", "dtend_local").astimezone(zone)
            end_day = end_instant.date()
            if (end_instant.hour, end_instant.minute, end_instant.second) != (0, 0, 0):
                end_day += timedelta(days=1)
            if end_day <= start_day:
                end_day = start_day + timedelta(days=1)
        else:
            end_day = start_day + timedelta(days=1)
        _require_dates(start_day, end_day)
        return [
            f"DTSTART;VALUE=DATE:{start_day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{end_day.strftime('%Y%m%d')}",
        ], False

    if previous_all_day and (dtstart is None or dtend is None):
        raise IcsError("converting an all-day event to a timed event needs dtstart and dtend")
    old_start = None if previous_all_day else _parsed_instant(parsed, "dtstart", "dtstart_local")
    old_end = None if previous_all_day else _parsed_instant(parsed, "dtend", "dtend_local")
    if dtstart is None:
        if old_start is None:
            raise IcsError("timed update needs dtstart")
        start = old_start
    else:
        parsed_start = parse_user_time(dtstart, zone)
        if parsed_start.instant is None:
            raise IcsError("timed dtstart needs a date-time")
        start = parsed_start.instant
    if dtend is None:
        if old_end is None:
            raise IcsError("timed update needs dtend")
        end = old_end
    else:
        parsed_end = parse_user_time(dtend, zone)
        if parsed_end.instant is None:
            raise IcsError("timed dtend needs a date-time")
        end = parsed_end.instant
    # Editing one edge keeps the other instant. Moving that edge past the
    # other side keeps the previous duration instead of storing a reversed span.
    if end <= start and (dtstart is None) != (dtend is None) and old_start is not None and old_end is not None:
        delta = old_end - old_start
        if delta <= timedelta(0):
            raise IcsError("dtend must be after dtstart")
        if dtstart is None:
            start = end - delta
        else:
            end = start + delta
    return _timed_lines(start, end, zone)


def _sequence_value(raw: str) -> str:
    try:
        return str(int(raw.strip()) + 1)
    except ValueError:
        return "1"


def _without_vtimezone(lines: list[str], tzid: str) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip().upper() != "BEGIN:VTIMEZONE":
            out.append(lines[index])
            index += 1
            continue
        block = [lines[index]]
        index += 1
        current = ""
        while index < len(lines):
            block.append(lines[index])
            name, _params, value = _parse_line(lines[index])
            if name == "TZID" and not current:
                current = value.strip()
            if lines[index].strip().upper() == "END:VTIMEZONE":
                index += 1
                break
            index += 1
        if current != tzid:
            out.extend(block)
    return out


def patch_vevent(
    raw: str,
    *,
    summary: str | None = None,
    dtstart: str | None = None,
    dtend: str | None = None,
    location: str | None = None,
    description: str | None = None,
    timezone: str | None = None,
    all_day: bool | None = None,
    status: str | None = None,
) -> str:
    """Replace the fields that were passed and keep every other property.

    ``RRULE``, ``EXDATE``, ``RDATE``, ``VALARM``, ``ATTENDEE``, ``UID``, and
    ``X-`` properties stay. ``SEQUENCE`` increments. ``DTSTAMP`` and
    ``LAST-MODIFIED`` become the current UTC time.
    """
    parsed = parse_vevent(raw, tz=timezone)
    zone = resolve_timezone(timezone or parsed.get("timezone"))
    times_change = dtstart is not None or dtend is not None or all_day is not None
    new_times: list[str] = []
    needs_zone = False
    if times_change:
        new_times, needs_zone = _replacement_times(
            parsed,
            dtstart=dtstart,
            dtend=dtend,
            all_day=all_day,
            zone=zone,
        )
    lines = _unfold(raw)
    if needs_zone:
        lines = _without_vtimezone(lines, zone_key(zone))
        insert_at = next(
            (index for index, line in enumerate(lines) if line.strip().upper() == "BEGIN:VEVENT"),
            len(lines),
        )
        vtz = build_vtimezone_lines(zone_key(zone))
        lines = lines[:insert_at] + vtz + lines[insert_at:]

    replacements: dict[str, list[str]] = {
        "DTSTAMP": [f"DTSTAMP:{_stamp()}"],
        "LAST-MODIFIED": [f"LAST-MODIFIED:{_stamp()}"],
    }
    if times_change:
        start_lines = [line for line in new_times if line.startswith("DTSTART")]
        end_lines = [line for line in new_times if line.startswith("DTEND")]
        replacements["DTSTART"] = start_lines
        replacements["DTEND"] = end_lines
        replacements["DURATION"] = []
    if summary is not None:
        replacements["SUMMARY"] = [f"SUMMARY:{_escape_text(summary)}"] if summary else []
    if location is not None:
        replacements["LOCATION"] = [f"LOCATION:{_escape_text(location)}"] if location else []
    if description is not None:
        replacements["DESCRIPTION"] = [f"DESCRIPTION:{_escape_text(description)}"] if description else []
    if status is not None:
        replacements["STATUS"] = [f"STATUS:{status.strip().upper()}"] if status.strip() else []

    out: list[str] = []
    depth = 0
    event_depth: int | None = None
    event_done = False
    seen: set[str] = set()
    for line in lines:
        upper = line.strip().upper()
        if upper.startswith("BEGIN:"):
            depth += 1
            if upper == "BEGIN:VEVENT" and event_depth is None and not event_done:
                event_depth = depth
            out.append(line.strip())
            continue
        if upper.startswith("END:"):
            if event_depth is not None and depth == event_depth and upper == "END:VEVENT":
                for name, payload in replacements.items():
                    if name == "SEQUENCE" or name in seen:
                        continue
                    out.extend(payload)
                    seen.add(name)
                if "SEQUENCE" not in seen:
                    out.append("SEQUENCE:1")
                out.append(line.strip())
                event_done = True
                event_depth = None
                depth -= 1
                continue
            depth = max(0, depth - 1)
            out.append(line.strip())
            continue
        if event_depth is None or depth != event_depth or event_done:
            out.append(line.strip())
            continue
        name, _params, value = _parse_line(line)
        if name == "SEQUENCE":
            out.append(f"SEQUENCE:{_sequence_value(value)}")
            seen.add("SEQUENCE")
            continue
        if name in replacements:
            if name not in seen:
                out.extend(replacements[name])
                seen.add(name)
            continue
        out.append(line.strip())
    return _fold(out)
