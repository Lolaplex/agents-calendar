"""FastMCP server. Tools mirror the CLI. Password never in responses."""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .client import CaldavClient, CaldavError, PreconditionFailed
from .config import ConfigError, load_settings
from .ics import IcsError

mcp = FastMCP("agents-calendar")
try:
    from . import __version__
    from .updates import attach_mcp_update_notice

    attach_mcp_update_notice(mcp, "agents-calendar", __version__)
except Exception:
    pass


def _client() -> CaldavClient:
    return CaldavClient(load_settings())


def _ok(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _err(exc: Exception) -> str:
    return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def calendar_calendars() -> str:
    """List calendar collections under CALDAV_URL."""
    try:
        return _ok(_client().calendars())
    except (ConfigError, CaldavError, IcsError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_list(start: str, end: str, calendar: str = "", timezone: str = "") -> str:
    """List VEVENTs between start and end. The server expands RRULE.

    Pass start and end as local wall time (2026-10-22T10:00:00) or as absolute
    instants (Z or a numeric offset). A date (2026-10-22) is 00:00 in the resolved
    zone. timezone is an IANA name. When it is empty the zone is CALDAV_TIMEZONE
    or timezone in the credentials file, else the calendar's calendar-timezone,
    else the host zone, else UTC. Naive values use that zone's offset on that
    date, including daylight-saving transitions.

    Each event has dtstart/dtend in UTC (or YYYY-MM-DD when all_day), dtstart_local
    and dtend_local with a numeric offset or a date, timezone (IANA name), all_day,
    and the calendar name. href and etag are required for update and delete.
    """
    try:
        return _ok(
            _client().list_events(
                start, end, calendar=calendar or None, timezone=timezone or None
            )
        )
    except (ConfigError, CaldavError, IcsError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_get(href: str, timezone: str = "") -> str:
    """Get one VEVENT by href.

    timezone is the IANA display zone for dtstart_local/dtend_local. Empty uses
    the same resolution order as calendar_list. all_day events return civil dates.
    Timed dtstart/dtend are UTC. The local fields include a numeric offset.
    """
    try:
        return _ok(_client().get_event(href, timezone=timezone or None))
    except (ConfigError, CaldavError, IcsError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_add(
    summary: str,
    dtstart: str,
    dtend: str,
    calendar: str = "",
    location: str = "",
    description: str = "",
    timezone: str = "",
    all_day: bool = False,
    status: str = "",
) -> str:
    """Create a VEVENT (If-None-Match: *).

    Pass dtstart and dtend as local wall time, for example 2026-11-29T16:00:00
    or 2026-11-29 16:00. Do not convert that wall time to UTC first. timezone is
    an IANA name; when empty, resolution is CALDAV_TIMEZONE / credentials file,
    then the calendar's calendar-timezone, then the host zone, then UTC.
    The offset is the IANA offset for that date, so daylight-saving transitions
    are correct. A value with Z or a numeric offset is that absolute instant.

    If the wall time does not exist (spring forward) or happens twice (fall back),
    the tool returns an error. Send an explicit offset for that instant instead.

    all_day=true, or date-only values such as 2026-11-29, stores VALUE=DATE.
    dtend is exclusive. The same date as dtstart means one civil day.

    Timed events are stored with TZID and VTIMEZONE so a weekly RRULE stays on
    the same wall clock across DST. The response includes UTC dtstart/dtend
    (civil dates when all_day), local fields with an offset, timezone, and all_day.
    """
    try:
        return _ok(
            _client().add_event(
                summary=summary,
                dtstart=dtstart,
                dtend=dtend,
                calendar=calendar or None,
                location=location,
                description=description,
                timezone=timezone or None,
                all_day=all_day,
                status=status,
            )
        )
    except (ConfigError, CaldavError, PreconditionFailed, IcsError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_update(
    href: str,
    etag: str,
    summary: str = "",
    dtstart: str = "",
    dtend: str = "",
    location: str = "",
    description: str = "",
    timezone: str = "",
    all_day: bool | None = None,
    status: str = "",
) -> str:
    """Update a VEVENT. href and etag come from calendar_list or calendar_get. If-Match is required.

    Empty strings leave that field unchanged. Naive dtstart/dtend are wall times
    in timezone, same rules as calendar_add. RRULE, EXDATE, VALARM, ATTENDEE,
    UID, and X- properties are preserved. SEQUENCE increments. Changing only one
    bound keeps the other instant when the span stays positive; if the edit would
    reverse the span, the previous duration is kept.
    """
    try:
        return _ok(
            _client().update_event(
                href,
                etag,
                summary=summary or None,
                dtstart=dtstart or None,
                dtend=dtend or None,
                location=location or None,
                description=description or None,
                timezone=timezone or None,
                all_day=all_day,
                status=status or None,
            )
        )
    except (ConfigError, CaldavError, PreconditionFailed, IcsError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_delete(href: str, etag: str) -> str:
    """Delete a VEVENT. href and etag come from calendar_list or calendar_get. If-Match is required."""
    try:
        return _ok(_client().delete_event(href, etag))
    except (ConfigError, CaldavError, PreconditionFailed, IcsError, ValueError) as exc:
        return _err(exc)
