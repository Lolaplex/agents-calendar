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
    """List VEVENTs between ISO start and end. Server expands recurrence.

    start and end accept ISO datetimes or date strings. Naive datetimes are localized
    using timezone (default: configured CALDAV_TIMEZONE or Europe/Berlin).
    Each returned event contains both dtstart/dtend in UTC and dtstart_local/dtend_local
    with timezone offset, plus the calendar collection name.
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
    """Get a single VEVENT by its href. Returns event details with both UTC and local times."""
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

    dtstart and dtend accept ISO datetimes (e.g. '2026-11-29T16:00:00' or '2026-11-29 16:00').
    Naive datetimes are deterministically localized in timezone (default: configured
    CALDAV_TIMEZONE or Europe/Berlin) and converted to UTC, correctly handling summer/winter
    daylight saving time (DST) shifts. Set all_day=True or pass date strings (e.g. '2026-11-29')
    for all-day events.
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

    Empty strings leave that field unchanged. Naive dtstart/dtend are localized in timezone.
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
