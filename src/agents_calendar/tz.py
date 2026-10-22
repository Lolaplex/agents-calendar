"""IANA time zones via the stdlib ``zoneinfo`` database.

Offsets are never hard-coded. Every UTC offset comes from ``zoneinfo`` (the
system tz database, or the ``tzdata`` package where the OS has none) or from a
``VTIMEZONE`` component carried on the calendar object.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class IcsError(ValueError):
    """Malformed iCalendar payload or a local time that cannot be stored safely."""


_UTC = dt_timezone.utc
_WEEKDAYS = ("SU", "MO", "TU", "WE", "TH", "FR", "SA")


def try_zone(name: str) -> ZoneInfo | None:
    raw = name.strip()
    if not raw or any(ch in raw for ch in "\r\n\t;:,"):
        return None
    try:
        return ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def require_zone(name: str) -> ZoneInfo:
    zone = try_zone(name)
    if zone is None:
        raise IcsError(f"unknown timezone '{name}'")
    return zone


def zone_key(zone: ZoneInfo) -> str:
    key = getattr(zone, "key", None)
    if isinstance(key, str) and key:
        return key
    return str(zone)


def resolve_timezone(
    tz: str | ZoneInfo | None = None,
    *,
    calendar_tz: str | None = None,
    configured: str | None = None,
) -> ZoneInfo:
    """Resolve an IANA zone.

    Order: explicit argument, configured zone (``CALDAV_TIMEZONE`` / credentials
    file, unless ``configured`` is already supplied), CalDAV ``calendar-timezone``,
    then the host system zone. The last resort is ``UTC``.
    """
    if isinstance(tz, ZoneInfo):
        return tz
    if isinstance(tz, str) and tz.strip():
        return require_zone(tz)
    if configured is None:
        from .config import configured_timezone

        configured = configured_timezone()
    if isinstance(configured, str) and configured.strip():
        return require_zone(configured)
    if isinstance(calendar_tz, str) and calendar_tz.strip():
        found = try_zone(calendar_tz)
        if found is not None:
            return found
    from .config import system_timezone_name

    return require_zone(system_timezone_name())


def is_date_only(value: str) -> bool:
    raw = value.strip()
    return bool(re.fullmatch(r"\d{8}", raw) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw))


def _parse_date(value: str) -> date:
    raw = value.strip()
    if re.fullmatch(r"\d{8}", raw):
        return datetime.strptime(raw, "%Y%m%d").date()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return date.fromisoformat(raw)
    raise IcsError(f"invalid date '{value}'")


def format_date(value: date) -> str:
    return value.isoformat()


def _fmt_hhmm(offset: timedelta) -> str:
    seconds = int(offset.total_seconds())
    sign = "+" if seconds >= 0 else "-"
    seconds = abs(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def localize_wall(naive: datetime, zone: ZoneInfo, *, strict: bool) -> datetime:
    """Attach ``zone`` to a naive wall time.

    ``strict`` rejects fall-back overlaps. Spring-forward gaps always raise:
    those clocks do not exist, so there is no offset that means that label.
    Non-strict ambiguous times use the first occurrence (the offset in effect
    before the clocks fell back). iCalendar has no fold bit.
    """
    if naive.tzinfo is not None:
        raise IcsError("expected a naive datetime")
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)
    off0 = first.utcoffset()
    off1 = second.utcoffset()
    if off0 is None or off1 is None:
        raise IcsError(f"timezone '{zone_key(zone)}' has no offset for {naive.isoformat()}")
    back = first.astimezone(_UTC).astimezone(zone).replace(tzinfo=None)
    exists = back == naive
    label = naive.strftime("%Y-%m-%dT%H:%M:%S")
    key = zone_key(zone)
    if off0 != off1 and exists:
        if strict:
            raise IcsError(
                f"ambiguous local time {label} in {key}: "
                f"this wall time occurs twice on the fall-back transition "
                f"({_fmt_hhmm(off0)} and {_fmt_hhmm(off1)}). "
                "Pass an explicit UTC offset."
            )
        return first
    if not exists:
        raise IcsError(
            f"nonexistent local time {label} in {key}: "
            "the clock skips this time on the spring-forward transition. "
            "Pass an explicit UTC offset."
        )
    return first


def is_ambiguous_wall(naive: datetime, zone: ZoneInfo) -> bool:
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)
    off0 = first.utcoffset()
    off1 = second.utcoffset()
    if off0 == off1:
        return False
    back = first.astimezone(_UTC).astimezone(zone).replace(tzinfo=None)
    return back == naive


def format_utc(instant: datetime) -> str:
    return instant.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_local(instant: datetime, zone: ZoneInfo) -> str:
    local = instant.astimezone(zone)
    stamp = local.strftime("%Y-%m-%dT%H:%M:%S")
    off = local.strftime("%z")
    if len(off) < 5:
        raise IcsError(f"missing UTC offset for {zone_key(zone)}")
    return f"{stamp}{off[:3]}:{off[3:]}"


def format_ics_instant(instant: datetime) -> str:
    return instant.astimezone(_UTC).strftime("%Y%m%dT%H%M%SZ")


def _with_seconds(text: str) -> str:
    """Give ``HH:MM`` a seconds field so Python 3.10 ``fromisoformat`` accepts it."""
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?!:)(.*)", text)
    if match is None:
        return text
    return f"{match.group(1)}:00{match.group(2)}"


def _parse_fixed_iso(raw: str) -> datetime:
    text = raw.strip().replace("Z", "+00:00").replace("z", "+00:00")
    if " " in text and "T" not in text.split(" ", 1)[0]:
        text = text.replace(" ", "T", 1)
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)"
        r"([+-])(\d{2}):?(\d{2})(?::?(\d{2}))?",
        text,
    )
    if match is None:
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise IcsError(f"invalid datetime '{raw}'") from exc
        if parsed.tzinfo is None:
            raise IcsError(f"invalid datetime '{raw}'")
        return parsed.astimezone(_UTC)
    naive = datetime.fromisoformat(_with_seconds(match.group(1)))
    sign = 1 if match.group(2) == "+" else -1
    seconds = sign * (
        int(match.group(3)) * 3600
        + int(match.group(4)) * 60
        + int(match.group(5) or 0)
    )
    return (naive - timedelta(seconds=seconds)).replace(tzinfo=_UTC)


def _parse_compact(raw: str) -> tuple[str, datetime]:
    """Return ``('utc'|'offset'|'naive', instant-or-naive)``."""
    match = re.fullmatch(r"(\d{8})T(\d{6})(Z|[+-]\d{2}:?\d{2}(?::?\d{2})?)?", raw, re.IGNORECASE)
    if match is None:
        raise IcsError(f"invalid datetime '{raw}'")
    naive = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    suffix = match.group(3)
    if suffix is None:
        return "naive", naive
    if suffix.upper() == "Z":
        return "utc", naive.replace(tzinfo=_UTC)
    sign = 1 if suffix[0] == "+" else -1
    digits = suffix[1:].replace(":", "")
    hours = int(digits[:2])
    minutes = int(digits[2:4]) if len(digits) >= 4 else 0
    seconds = int(digits[4:6]) if len(digits) >= 6 else 0
    offset = sign * (hours * 3600 + minutes * 60 + seconds)
    return "offset", (naive - timedelta(seconds=offset)).replace(tzinfo=_UTC)


@dataclass(frozen=True)
class UserTime:
    """A user-supplied start or end. Dates are civil; instants are UTC."""

    all_day: bool
    civil: date | None
    instant: datetime | None
    zone: ZoneInfo


def parse_user_time(value: str, zone: ZoneInfo) -> UserTime:
    """Parse one user datetime.

    Date-only values are civil dates. Naive datetimes are wall times in
    ``zone`` and are rejected when that wall time is skipped or repeated.
    ``Z`` and numeric offsets are absolute instants.
    """
    raw = value.strip()
    if not raw:
        raise IcsError("empty datetime")
    if is_date_only(raw):
        return UserTime(True, _parse_date(raw), None, zone)
    upper = raw.upper()
    if re.fullmatch(r"\d{8}T\d{6}(Z|[+-]\d{2}:?\d{2}(?::?\d{2})?)?", upper):
        kind, parsed = _parse_compact(upper)
        if kind == "naive":
            aware = localize_wall(parsed, zone, strict=True)
            return UserTime(False, None, aware.astimezone(_UTC), zone)
        return UserTime(False, None, parsed.astimezone(_UTC), zone)
    iso = raw.replace("Z", "+00:00").replace("z", "+00:00")
    if " " in iso[:11]:
        iso = iso.replace(" ", "T", 1)
    iso = _with_seconds(iso)
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        try:
            return UserTime(False, None, _parse_fixed_iso(raw), zone)
        except IcsError as exc:
            raise IcsError(f"invalid datetime '{value}'") from exc
    if parsed.tzinfo is None:
        aware = localize_wall(parsed, zone, strict=True)
        return UserTime(False, None, aware.astimezone(_UTC), zone)
    return UserTime(False, None, parsed.astimezone(_UTC), zone)


def to_caldav_utc(value: str, zone: ZoneInfo) -> str:
    """UTC stamp for a CalDAV time-range. A date is local midnight."""
    parsed = parse_user_time(value, zone)
    if parsed.all_day and parsed.civil is not None:
        midnight = datetime(parsed.civil.year, parsed.civil.month, parsed.civil.day)
        aware = localize_wall(midnight, zone, strict=True)
        return format_ics_instant(aware)
    if parsed.instant is None:
        raise IcsError(f"invalid datetime '{value}'")
    return format_ics_instant(parsed.instant)


def format_zoned_line(name: str, instant: datetime, zone: ZoneInfo) -> tuple[str, bool]:
    """Property line, and whether it references ``TZID``.

    Ambiguous wall times are stored as UTC so the fall-back instant is not
    lost. ``DTSTART;TZID`` cannot represent both occurrences.
    """
    local = instant.astimezone(zone)
    naive = local.replace(tzinfo=None)
    if is_ambiguous_wall(naive, zone):
        return f"{name}:{format_ics_instant(instant)}", False
    stamp = naive.strftime("%Y%m%dT%H%M%S")
    return f"{name};TZID={zone_key(zone)}:{stamp}", True


def format_utc_offset(seconds: int) -> str:
    sign = "+" if seconds >= 0 else "-"
    remaining = abs(int(seconds))
    hours, rem = divmod(remaining, 3600)
    minutes, secs = divmod(rem, 60)
    if secs:
        return f"{sign}{hours:02d}{minutes:02d}{secs:02d}"
    return f"{sign}{hours:02d}{minutes:02d}"


def parse_utc_offset(value: str) -> int:
    match = re.fullmatch(r"([+-])(\d{2}):?(\d{2}):?(\d{2})?", value.strip())
    if match is None:
        raise IcsError(f"invalid UTC offset '{value}'")
    sign = 1 if match.group(1) == "+" else -1
    return sign * (
        int(match.group(2)) * 3600
        + int(match.group(3)) * 60
        + int(match.group(4) or 0)
    )


@dataclass(frozen=True)
class _Rule:
    kind: str
    month: int = 0
    week: int = 0
    weekday: int = 0
    yday: int = 0
    once: datetime | None = None
    hour: int = 2
    minute: int = 0
    second: int = 0


@dataclass(frozen=True)
class _Obs:
    offset_from: int
    offset_to: int
    name: str
    is_dst: bool
    rule: _Rule


def _posix_name(text: str, index: int) -> tuple[str, int]:
    if index >= len(text):
        raise IcsError("truncated POSIX TZ string")
    if text[index] == "<":
        end = text.find(">", index + 1)
        if end < 0:
            raise IcsError("unterminated POSIX TZ name")
        return text[index + 1 : end], end + 1
    start = index
    while index < len(text) and text[index].isalpha():
        index += 1
    if index - start < 3:
        raise IcsError(f"invalid POSIX TZ name in '{text}'")
    return text[start:index], index


def _posix_offset(text: str, index: int) -> tuple[int, int]:
    """Parse a POSIX offset (hours west of UTC) into ISO east-of-UTC seconds."""
    if index >= len(text):
        raise IcsError("missing POSIX TZ offset")
    sign = 1
    if text[index] in "+-":
        if text[index] == "-":
            sign = -1
        index += 1
    start = index
    while index < len(text) and text[index].isdigit():
        index += 1
    if index == start:
        raise IcsError(f"invalid POSIX TZ offset in '{text}'")
    hours = int(text[start:index])
    minutes = 0
    seconds = 0
    if index < len(text) and text[index] == ":":
        index += 1
        start = index
        while index < len(text) and text[index].isdigit():
            index += 1
        minutes = int(text[start:index] or "0")
        if index < len(text) and text[index] == ":":
            index += 1
            start = index
            while index < len(text) and text[index].isdigit():
                index += 1
            seconds = int(text[start:index] or "0")
    posix_seconds = sign * (hours * 3600 + minutes * 60 + seconds)
    return -posix_seconds, index


def _clock(text: str) -> tuple[int, int, int]:
    sign = 1
    if text[:1] in "+-":
        if text[0] == "-":
            sign = -1
        text = text[1:]
    parts = text.split(":")
    if not parts or not parts[0].isdigit():
        raise IcsError(f"invalid transition time '{text}'")
    hours = sign * int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    seconds = int(parts[2]) if len(parts) > 2 and parts[2] else 0
    if sign < 0:
        minutes = -minutes
        seconds = -seconds
    return hours, minutes, seconds


def _parse_rule(spec: str) -> _Rule:
    clock = "2"
    body = spec
    if "/" in spec:
        body, clock = spec.split("/", 1)
    hour, minute, second = _clock(clock)
    if body.startswith("M"):
        month_s, week_s, day_s = body[1:].split(".")
        return _Rule(
            "month",
            month=int(month_s),
            week=int(week_s),
            weekday=int(day_s),
            hour=hour,
            minute=minute,
            second=second,
        )
    if body.startswith("J"):
        return _Rule("julian_noleap", yday=int(body[1:]), hour=hour, minute=minute, second=second)
    if body.isdigit():
        return _Rule("julian", yday=int(body), hour=hour, minute=minute, second=second)
    raise IcsError(f"unsupported POSIX TZ rule '{spec}'")


def _specs_from_posix(posix: str) -> list[_Obs]:
    text = posix.strip()
    if not text:
        raise IcsError("empty POSIX TZ string")
    std_name, index = _posix_name(text, 0)
    std_off, index = _posix_offset(text, index)
    if index >= len(text):
        return [_standard(std_name, std_off)]
    if text[index] == ",":
        return [_standard(std_name, std_off)]
    _dst_name, index = _posix_name(text, index)
    if index < len(text) and text[index] in "+-" or text[index].isdigit():
        dst_off, index = _posix_offset(text, index)
    else:
        dst_off = std_off + 3600
    if index >= len(text) or text[index] != ",":
        return [_standard(std_name, std_off)]
    rules = text[index + 1 :]
    start_s, _, end_s = rules.partition(",")
    if not end_s:
        raise IcsError(f"POSIX TZ rule needs a DST end in '{posix}'")
    return [
        _Obs(std_off, dst_off, _dst_name, True, _parse_rule(start_s)),
        _Obs(dst_off, std_off, std_name, False, _parse_rule(end_s)),
    ]


def _standard(name: str, offset: int) -> _Obs:
    return _Obs(
        offset,
        offset,
        name,
        False,
        _Rule("once", once=datetime(1970, 1, 1, 0, 0, 0), hour=0, minute=0, second=0),
    )


def _nth_weekday(year: int, month: int, week: int, posix_weekday: int) -> date:
    python_weekday = (posix_weekday + 6) % 7
    if week == 5:
        if month == 12:
            cursor = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            cursor = date(year, month + 1, 1) - timedelta(days=1)
        delta = (cursor.weekday() - python_weekday) % 7
        return cursor - timedelta(days=delta)
    cursor = date(year, month, 1)
    delta = (python_weekday - cursor.weekday()) % 7
    found = cursor + timedelta(days=delta + (week - 1) * 7)
    if found.month != month:
        raise IcsError(f"no weekday {posix_weekday} in week {week} of {year}-{month:02d}")
    return found


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _occurrence(rule: _Rule, year: int) -> datetime:
    if rule.kind == "once":
        if rule.once is None:
            raise IcsError("transition is missing DTSTART")
        return rule.once
    if rule.kind == "month":
        found = _nth_weekday(year, rule.month, rule.week, rule.weekday)
    elif rule.kind == "julian":
        found = date(year, 1, 1) + timedelta(days=rule.yday)
    elif rule.kind == "julian_noleap":
        extra = 1 if _leap(year) and rule.yday >= 60 else 0
        found = date(year, 1, 1) + timedelta(days=rule.yday - 1 + extra)
    else:
        raise IcsError(f"unsupported transition rule '{rule.kind}'")
    return datetime(found.year, found.month, found.day, rule.hour, rule.minute, rule.second)


def _rrule(rule: _Rule) -> str | None:
    if rule.kind != "month":
        return None
    nth = -1 if rule.week == 5 else rule.week
    return (
        f"RRULE:FREQ=YEARLY;BYMONTH={rule.month};BYDAY={nth}{_WEEKDAYS[rule.weekday]}"
    )


def _render_specs(zone_name: str, specs: Iterable[_Obs]) -> list[str]:
    lines = ["BEGIN:VTIMEZONE", f"TZID:{zone_name}", f"X-LIC-LOCATION:{zone_name}"]
    for obs in specs:
        kind = "DAYLIGHT" if obs.is_dst else "STANDARD"
        when = obs.rule.once if obs.rule.kind == "once" and obs.rule.once else _occurrence(obs.rule, 1970)
        lines.append(f"BEGIN:{kind}")
        lines.append(f"DTSTART:{when.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"TZOFFSETFROM:{format_utc_offset(obs.offset_from)}")
        lines.append(f"TZOFFSETTO:{format_utc_offset(obs.offset_to)}")
        if obs.name:
            lines.append(f"TZNAME:{obs.name}")
        rule = _rrule(obs.rule)
        if rule:
            lines.append(rule)
        lines.append(f"END:{kind}")
    lines.append("END:VTIMEZONE")
    return lines


def _offset_at(transitions: list[tuple[datetime, int]], moment: datetime) -> int | None:
    active: int | None = None
    for instant, offset in transitions:
        if instant <= moment:
            active = offset
        else:
            break
    return active


def matching_offsets(specs: list[_Obs], local: datetime) -> list[int]:
    """Offsets for which ``local`` is a real wall time. Empty means a gap."""
    transitions: list[tuple[datetime, int]] = []
    years = range(local.year - 1, local.year + 2)
    for obs in specs:
        instants: list[datetime]
        if obs.rule.kind == "once":
            instants = [_occurrence(obs.rule, local.year)]
        else:
            instants = [_occurrence(obs.rule, year) for year in years]
        for start in instants:
            transitions.append((start - timedelta(seconds=obs.offset_from), obs.offset_to))
    transitions.sort(key=lambda item: item[0])
    found: list[int] = []
    for offset in sorted({obs.offset_to for obs in specs} | {obs.offset_from for obs in specs}):
        active = _offset_at(transitions, local - timedelta(seconds=offset))
        if active == offset and offset not in found:
            found.append(offset)
    found.sort(key=lambda offset: local - timedelta(seconds=offset))
    return found


def instant_from_specs(specs: list[_Obs], local: datetime, *, strict: bool) -> datetime:
    matches = matching_offsets(specs, local)
    label = local.strftime("%Y-%m-%dT%H:%M:%S")
    if not matches:
        raise IcsError(
            f"nonexistent local time {label} in this VTIMEZONE: "
            "the clock skips this time on the spring-forward transition. "
            "Pass an explicit UTC offset."
        )
    if len(matches) > 1:
        if strict:
            shown = ", ".join(format_utc_offset(item) for item in matches)
            raise IcsError(
                f"ambiguous local time {label} in this VTIMEZONE: "
                f"this wall time occurs twice on the fall-back transition ({shown}). "
                "Pass an explicit UTC offset."
            )
        offset = matches[0]
    else:
        offset = matches[0]
    return (local - timedelta(seconds=offset)).replace(tzinfo=_UTC)


def _zone_samples(zone: ZoneInfo, start_year: int = 2024, end_year: int = 2028) -> list[tuple[datetime, datetime]]:
    samples: list[tuple[datetime, datetime]] = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            for day in (1, 10, 20, 28):
                naive = datetime(year, month, day, 12, 0, 0)
                first = naive.replace(tzinfo=zone, fold=0)
                second = naive.replace(tzinfo=zone, fold=1)
                if first.utcoffset() != second.utcoffset():
                    continue
                back = first.astimezone(_UTC).astimezone(zone).replace(tzinfo=None)
                if back != naive:
                    continue
                samples.append((naive, first.astimezone(_UTC)))
    return samples


def _matches_zone(zone: ZoneInfo, specs: list[_Obs]) -> bool:
    samples = _zone_samples(zone)
    if len(samples) < 24:
        return False
    for naive, expected in samples:
        try:
            got = instant_from_specs(specs, naive, strict=True)
        except IcsError:
            return False
        if got != expected:
            return False
    return True


def _locate_tzif(key: str) -> Path:
    import zoneinfo

    safe = key.strip().replace("\\", "/")
    if not safe or safe.startswith("/") or ".." in safe.split("/"):
        raise IcsError(f"unknown timezone '{key}'")
    for base in zoneinfo.TZPATH:
        path = Path(base) / safe
        if path.is_file():
            return path
    raise IcsError(
        f"no IANA tz data file for '{key}'. Install the tzdata package or the system time zone database."
    )


def _read_tzif(key: str) -> tuple[list[tuple[int, int, bool, str]], str]:
    data = _locate_tzif(key).read_bytes()
    if len(data) < 44 or data[:4] != b"TZif":
        raise IcsError(f"invalid tz data for '{key}'")

    def header(offset: int) -> tuple[bytes, tuple[int, int, int, int, int, int], int]:
        if offset + 44 > len(data):
            raise IcsError(f"truncated tz data for '{key}'")
        version = data[offset + 4 : offset + 5]
        counts = struct.unpack(">6I", data[offset + 20 : offset + 44])
        return version, counts, offset + 44

    version, counts, offset = header(0)
    isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
    offset += timecnt * 4 + timecnt + typecnt * 6 + charcnt + leapcnt * 8 + isstdcnt + isutcnt
    if version in (b"2", b"3"):
        _version, counts, offset = header(offset)
        isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
        time_size = 8
    else:
        offset = 44
        time_size = 4
    if timecnt:
        fmt = f">{timecnt}{'q' if time_size == 8 else 'i'}"
        times = struct.unpack(fmt, data[offset : offset + time_size * timecnt])
        offset += time_size * timecnt
    else:
        times = ()
    type_index = data[offset : offset + timecnt]
    offset += timecnt
    infos: list[tuple[int, bool, int]] = []
    for _ in range(typecnt):
        utoff, isdst, abbrind = struct.unpack(">iBB", data[offset : offset + 6])
        offset += 6
        infos.append((utoff, bool(isdst), abbrind))
    abbreviations = data[offset : offset + charcnt]
    transitions: list[tuple[int, int, bool, str]] = []
    for index, moment in enumerate(times):
        info_index = type_index[index]
        if info_index >= len(infos):
            raise IcsError(f"invalid tz data for '{key}'")
        utoff, isdst, abbrind = infos[info_index]
        end = abbreviations.find(b"\x00", abbrind)
        if end < 0:
            end = len(abbreviations)
        name = abbreviations[abbrind:end].decode("ascii", errors="replace")
        transitions.append((int(moment), utoff, isdst, name))
    posix = ""
    if data.endswith(b"\n"):
        previous = data.rfind(b"\n", 0, len(data) - 1)
        if previous >= 0:
            posix = data[previous + 1 : -1].decode("ascii", errors="replace")
    return transitions, posix


def _specs_from_transitions(transitions: list[tuple[int, int, bool, str]]) -> list[_Obs]:
    if not transitions:
        raise IcsError("time zone has no transitions")
    window_start = int(datetime(1970, 1, 1, tzinfo=_UTC).timestamp())
    window_end = 2**31 - 1
    initial_offset = transitions[0][1]
    initial_dst = transitions[0][2]
    initial_name = transitions[0][3]
    for moment, offset, isdst, name in transitions:
        if moment <= window_start:
            initial_offset = offset
            initial_dst = isdst
            initial_name = name
        else:
            break
    specs = [
        _Obs(
            initial_offset,
            initial_offset,
            initial_name,
            initial_dst,
            _Rule("once", once=datetime(1970, 1, 1, 0, 0, 0), hour=0, minute=0, second=0),
        )
    ]
    previous = initial_offset
    for moment, offset, isdst, name in transitions:
        if moment < window_start or moment >= window_end:
            continue
        utc = datetime.fromtimestamp(moment, tz=_UTC)
        local_before = (utc + timedelta(seconds=previous)).replace(tzinfo=None)
        specs.append(
            _Obs(
                previous,
                offset,
                name,
                isdst,
                _Rule("once", once=local_before, hour=local_before.hour, minute=local_before.minute, second=local_before.second),
            )
        )
        previous = offset
    return specs


def _byday(token: str) -> tuple[int, int]:
    match = re.fullmatch(r"([+-]?\d)?(SU|MO|TU|WE|TH|FR|SA)", token.strip().upper())
    if match is None:
        raise IcsError(f"unsupported BYDAY '{token}'")
    nth = int(match.group(1) or "0")
    weekday = _WEEKDAYS.index(match.group(2))
    week = 5 if nth == -1 else nth
    if week not in (1, 2, 3, 4, 5):
        raise IcsError(f"unsupported BYDAY '{token}'")
    return week, weekday


def specs_from_vtimezone(text: str) -> list[_Obs]:
    """Observances inside one ``VTIMEZONE`` block (or a calendar that contains it)."""
    lines = _logical_lines(text)
    specs: list[_Obs] = []
    current: dict[str, str] | None = None
    kind = ""
    for line in lines:
        upper = line.upper()
        if upper.startswith("BEGIN:STANDARD") or upper.startswith("BEGIN:DAYLIGHT"):
            current = {}
            kind = "DAYLIGHT" if upper.endswith("DAYLIGHT") else "STANDARD"
            continue
        if upper in ("END:STANDARD", "END:DAYLIGHT"):
            if current is None:
                raise IcsError("VTIMEZONE ended an observance that never began")
            if "DTSTART" not in current or "TZOFFSETTO" not in current:
                raise IcsError("VTIMEZONE observance is missing DTSTART or TZOFFSETTO")
            start = datetime.strptime(current["DTSTART"], "%Y%m%dT%H%M%S")
            offset_to = parse_utc_offset(current["TZOFFSETTO"])
            offset_from = parse_utc_offset(current.get("TZOFFSETFROM", current["TZOFFSETTO"]))
            rule = _rule_from_observance(start, current.get("RRULE", ""))
            specs.append(
                _Obs(offset_from, offset_to, current.get("TZNAME", ""), kind == "DAYLIGHT", rule)
            )
            current = None
            continue
        if current is None or ":" not in line:
            continue
        name, _, value = line.partition(":")
        current[name.split(";", 1)[0].upper()] = value.strip()
    if not specs:
        raise IcsError("VTIMEZONE has no STANDARD or DAYLIGHT observance")
    return specs


def _rule_from_observance(start: datetime, rrule: str) -> _Rule:
    if not rrule:
        return _Rule(
            "once",
            once=start,
            hour=start.hour,
            minute=start.minute,
            second=start.second,
        )
    parts: dict[str, str] = {}
    for item in rrule.split(";"):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        parts[key.strip().upper()] = val.strip()
    if parts.get("FREQ", "").upper() != "YEARLY":
        raise IcsError(f"unsupported VTIMEZONE RRULE '{rrule}'")
    if parts.get("INTERVAL") not in (None, "", "1"):
        raise IcsError(f"unsupported VTIMEZONE RRULE '{rrule}'")
    hour, minute, second = start.hour, start.minute, start.second
    if "BYMONTH" in parts and "BYDAY" in parts:
        month = int(parts["BYMONTH"].split(",")[0])
        week, weekday = _byday(parts["BYDAY"].split(",")[0])
        return _Rule("month", month=month, week=week, weekday=weekday, hour=hour, minute=minute, second=second)
    if "BYYEARDAY" in parts:
        return _Rule("julian", yday=int(parts["BYYEARDAY"].split(",")[0]), hour=hour, minute=minute, second=second)
    raise IcsError(f"unsupported VTIMEZONE RRULE '{rrule}'")


def _logical_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        elif line != "":
            lines.append(line)
    return lines


def vtimezone_map(text: str) -> dict[str, str]:
    """Map ``TZID`` to the raw ``VTIMEZONE`` block."""
    lines = _logical_lines(text)
    found: dict[str, str] = {}
    collecting: list[str] | None = None
    tzid = ""
    for line in lines:
        upper = line.upper()
        if upper == "BEGIN:VTIMEZONE":
            collecting = [line]
            tzid = ""
            continue
        if collecting is None:
            continue
        collecting.append(line)
        if upper.startswith("TZID:") and not tzid:
            tzid = line.split(":", 1)[1].strip()
        if upper == "END:VTIMEZONE":
            if tzid:
                found[tzid] = "\r\n".join(collecting)
            collecting = None
    return found


def iana_from_calendar_timezone(text: str) -> str | None:
    """Return an IANA id from a CalDAV ``calendar-timezone`` body, if it has one."""
    if not text.strip():
        return None
    blocks = vtimezone_map(text)
    for tzid in blocks:
        if try_zone(tzid) is not None:
            return tzid.strip()
    for line in _logical_lines(text):
        if line.upper().startswith("X-WR-TIMEZONE:"):
            candidate = line.split(":", 1)[1].strip()
            if try_zone(candidate) is not None:
                return candidate
    return None


def build_vtimezone_lines(zone_name: str) -> list[str]:
    """``VTIMEZONE`` lines whose offsets match ``zoneinfo`` for this IANA id."""
    zone = require_zone(zone_name)
    key = zone_key(zone)
    transitions, posix = _read_tzif(key)
    if posix.strip():
        try:
            posix_specs = _specs_from_posix(posix)
        except IcsError:
            posix_specs = []
        if posix_specs and _matches_zone(zone, posix_specs):
            rendered = _render_specs(key, posix_specs)
            try:
                reparsed = specs_from_vtimezone("\r\n".join(rendered))
            except IcsError:
                reparsed = []
            if reparsed and _matches_zone(zone, reparsed):
                return rendered
    transition_specs = _specs_from_transitions(transitions)
    if not _matches_zone(zone, transition_specs):
        raise IcsError(f"cannot build a VTIMEZONE that matches IANA data for '{key}'")
    return _render_specs(key, transition_specs)


def instant_from_vtimezone(block: str, local: datetime, *, strict: bool) -> datetime:
    return instant_from_specs(specs_from_vtimezone(block), local, strict=strict)


def interpret_zoned_value(
    value: str,
    *,
    tzid: str,
    vtimezones: dict[str, str],
    strict: bool,
) -> datetime:
    """Resolve a floating iCalendar date-time that names ``TZID``."""
    raw = value.strip().upper()
    if raw.endswith("Z") or re.search(r"[+-]\d{2}:?\d{2}$", raw):
        kind, parsed = _parse_compact(raw) if "T" in raw and "-" not in raw[:4] else ("offset", _parse_fixed_iso(value))
        if kind == "naive":
            raise IcsError(f"invalid datetime '{value}'")
        return parsed.astimezone(_UTC)
    if re.fullmatch(r"\d{8}T\d{6}", raw):
        naive = datetime.strptime(raw, "%Y%m%dT%H%M%S")
    else:
        iso = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError as exc:
            raise IcsError(f"invalid datetime '{value}'") from exc
        if parsed.tzinfo is not None:
            return parsed.astimezone(_UTC)
        naive = parsed
    iana = try_zone(tzid)
    if iana is not None:
        return localize_wall(naive, iana, strict=strict).astimezone(_UTC)
    block = vtimezones.get(tzid)
    if block is None:
        raise IcsError(f"unknown TZID '{tzid}' and no matching VTIMEZONE")
    return instant_from_vtimezone(block, naive, strict=strict)
