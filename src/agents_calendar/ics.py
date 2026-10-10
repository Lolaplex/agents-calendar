import re
import uuid
import zoneinfo
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any


class IcsError(ValueError):
    """Malformed iCalendar payload."""


def resolve_timezone(tz: str | zoneinfo.ZoneInfo | None = None) -> zoneinfo.ZoneInfo:
    if isinstance(tz, zoneinfo.ZoneInfo):
        return tz
    if tz and isinstance(tz, str) and tz.strip():
        try:
            return zoneinfo.ZoneInfo(tz.strip())
        except Exception as exc:
            raise IcsError(f"unknown timezone '{tz}'") from exc
    from .config import get_default_timezone

    default_name = get_default_timezone()
    try:
        return zoneinfo.ZoneInfo(default_name)
    except Exception:
        return zoneinfo.ZoneInfo("Europe/Berlin")


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


def is_date_only(value: str) -> bool:
    raw = value.strip()
    return bool(re.fullmatch(r"\d{8}", raw) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw))


def parse_iso(value: str, default_tz: str | zoneinfo.ZoneInfo | None = None) -> datetime:
    raw = value.strip()
    if not raw:
        raise IcsError("empty datetime")

    # Compact format: 20260914T080000Z or 20260914T080000
    compact = re.fullmatch(r"(\d{8})T(\d{6})(Z)?", raw)
    if compact:
        dt = datetime.strptime(compact.group(1) + compact.group(2), "%Y%m%d%H%M%S")
        if compact.group(3):
            return dt.replace(tzinfo=dt_timezone.utc)
        tz = resolve_timezone(default_tz)
        return dt.replace(tzinfo=tz).astimezone(dt_timezone.utc)

    # Date-only compact: 20260928
    if re.fullmatch(r"\d{8}", raw):
        return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=dt_timezone.utc)

    # Date-only ISO: 2026-09-28
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)

    iso = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise IcsError(f"invalid datetime '{value}'") from exc

    if parsed.tzinfo is None:
        tz = resolve_timezone(default_tz)
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(dt_timezone.utc)


def to_caldav_utc(value: str, default_tz: str | zoneinfo.ZoneInfo | None = None) -> str:
    return parse_iso(value, default_tz=default_tz).strftime("%Y%m%dT%H%M%SZ")


def to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_iso_local(dt: datetime, default_tz: str | zoneinfo.ZoneInfo | None = None) -> str:
    tz = resolve_timezone(default_tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(tz).isoformat()


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
    timezone: str | None = None,
    all_day: bool = False,
    status: str = "",
) -> str:
    tz = resolve_timezone(timezone)
    is_allday = all_day or (is_date_only(dtstart) and (not dtend or is_date_only(dtend)))

    if is_allday:
        s_clean = dtstart.strip().replace("-", "")[:8]
        if dtend:
            e_clean = dtend.strip().replace("-", "")[:8]
        else:
            s_dt = datetime.strptime(s_clean, "%Y%m%d")
            e_clean = (s_dt + timedelta(days=1)).strftime("%Y%m%d")
        start_line = f"DTSTART;VALUE=DATE:{s_clean}"
        end_line = f"DTEND;VALUE=DATE:{e_clean}"
    else:
        start = to_caldav_utc(dtstart, default_tz=tz)
        end = to_caldav_utc(dtend, default_tz=tz)
        start_line = f"DTSTART:{start}"
        end_line = f"DTEND:{end}"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lolaplex//agents-calendar//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        start_line,
        end_line,
        f"SUMMARY:{_escape_text(summary)}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape_text(location)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape_text(description)}")
    if status:
        lines.append(f"STATUS:{status.strip().upper()}")
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


def _parse_line(line: str) -> tuple[str, dict[str, str], str]:
    colon_idx = line.find(":")
    if colon_idx == -1:
        return "", {}, ""
    head = line[:colon_idx]
    val = line[colon_idx + 1 :]
    parts = head.split(";")
    name = parts[0].strip().upper()
    params: dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip().upper()] = v.strip().strip("'\"")
    return name, params, val


def parse_vevent(raw: str, tz: str | zoneinfo.ZoneInfo | None = None) -> dict[str, Any]:
    """Parse the first VEVENT in an iCalendar payload."""
    lines = _unfold(raw)
    in_event = False
    fields: dict[str, tuple[dict[str, str], str]] = {}
    for line in lines:
        upper = line.strip().upper()
        if upper == "BEGIN:VEVENT":
            in_event = True
            continue
        if upper == "END:VEVENT":
            break
        if not in_event or ":" not in line:
            continue
        name, params, value = _parse_line(line)
        if name:
            fields[name] = (params, value)

    if "UID" not in fields:
        raise IcsError("VEVENT missing UID")

    target_tz = resolve_timezone(tz)
    start_params, start_raw = fields.get("DTSTART", ({}, ""))
    end_params, end_raw = fields.get("DTEND", ({}, ""))

    all_day = (
        start_params.get("VALUE", "").upper() == "DATE"
        or end_params.get("VALUE", "").upper() == "DATE"
        or (bool(start_raw) and is_date_only(start_raw))
    )

    event_start_tz = resolve_timezone(start_params.get("TZID") or target_tz)
    event_end_tz = resolve_timezone(end_params.get("TZID") or event_start_tz)

    dtstart_utc = ""
    dtstart_local = ""
    if start_raw:
        dt_start = parse_iso(start_raw, default_tz=event_start_tz)
        dtstart_utc = to_iso_z(dt_start)
        if all_day:
            raw_clean = start_raw.strip()
            dtstart_local = raw_clean if "-" in raw_clean else f"{raw_clean[:4]}-{raw_clean[4:6]}-{raw_clean[6:8]}"
        else:
            dtstart_local = dt_start.astimezone(target_tz).isoformat()

    dtend_utc = ""
    dtend_local = ""
    if end_raw:
        dt_end = parse_iso(end_raw, default_tz=event_end_tz)
        dtend_utc = to_iso_z(dt_end)
        if all_day:
            raw_clean = end_raw.strip()
            dtend_local = raw_clean if "-" in raw_clean else f"{raw_clean[:4]}-{raw_clean[4:6]}-{raw_clean[6:8]}"
        else:
            dtend_local = dt_end.astimezone(target_tz).isoformat()

    summary_raw = fields.get("SUMMARY", ({}, ""))[1]
    location_raw = fields.get("LOCATION", ({}, ""))[1]
    description_raw = fields.get("DESCRIPTION", ({}, ""))[1]
    status_raw = fields.get("STATUS", ({}, ""))[1]

    event: dict[str, Any] = {
        "uid": fields["UID"][1],
        "summary": _unescape_text(summary_raw),
        "dtstart": dtstart_utc,
        "dtstart_local": dtstart_local,
        "dtend": dtend_utc,
        "dtend_local": dtend_local,
        "timezone": getattr(target_tz, "key", str(target_tz)),
        "all_day": all_day,
        "location": _unescape_text(location_raw),
        "description": _unescape_text(description_raw),
    }
    if status_raw:
        event["status"] = status_raw.strip().upper()
    return event


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
    parsed = parse_vevent(raw, tz=timezone)
    use_allday = parsed["all_day"] if all_day is None else all_day
    use_status = parsed.get("status", "") if status is None else status
    use_tz = timezone or parsed.get("timezone")

    # If dtstart is not provided, use existing dtstart_local or dtstart
    orig_dtstart = parsed["dtstart_local"] if use_allday else parsed["dtstart"]
    orig_dtend = parsed["dtend_local"] if use_allday else parsed["dtend"]

    return emit_vevent(
        uid=parsed["uid"],
        summary=parsed["summary"] if summary is None else summary,
        dtstart=orig_dtstart if dtstart is None else dtstart,
        dtend=orig_dtend if dtend is None else dtend,
        location=parsed["location"] if location is None else location,
        description=parsed["description"] if description is None else description,
        timezone=use_tz,
        all_day=use_allday,
        status=use_status,
    )
