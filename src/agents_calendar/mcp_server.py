"""FastMCP server. Tools mirror the CLI. Password never in responses."""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .client import CaldavClient, CaldavError, PreconditionFailed
from .config import ConfigError, load_settings
from .ics import IcsError

mcp = FastMCP("agents-calendar")


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
def calendar_list(start: str, end: str) -> str:
    """List VEVENTs between ISO start and end. Server expands recurrence."""
    try:
        return _ok(_client().list_events(start, end))
    except (ConfigError, CaldavError, IcsError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_add(
    summary: str,
    dtstart: str,
    dtend: str,
    location: str = "",
    description: str = "",
) -> str:
    """Create a VEVENT. Uses If-None-Match so existing UIDs are not overwritten."""
    try:
        return _ok(
            _client().add_event(
                summary=summary,
                dtstart=dtstart,
                dtend=dtend,
                location=location,
                description=description,
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
) -> str:
    """Update a VEVENT. href and etag come from calendar_list. If-Match is required."""
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
            )
        )
    except (ConfigError, CaldavError, PreconditionFailed, IcsError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def calendar_delete(href: str, etag: str) -> str:
    """Delete a VEVENT. href and etag come from calendar_list. If-Match is required."""
    try:
        return _ok(_client().delete_event(href, etag))
    except (ConfigError, CaldavError, PreconditionFailed, IcsError, ValueError) as exc:
        return _err(exc)
