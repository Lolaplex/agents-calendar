"""CLI for agents-calendar."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .client import CaldavClient, CaldavError, PreconditionFailed
from .config import ConfigError, load_settings
from .ics import IcsError


def help_json() -> dict[str, Any]:
    return {
        "name": "agents-calendar",
        "version": __version__,
        "commands": {
            "calendars": {
                "usage": "agents-calendar calendars",
                "description": "List calendar collections under CALDAV_URL.",
            },
            "list": {
                "usage": "agents-calendar list --from ISO --to ISO",
                "description": "List VEVENTs in the time range. Server expands recurrence.",
            },
            "add": {
                "usage": "agents-calendar add --summary TEXT --dtstart ISO --dtend ISO [--location TEXT] [--description TEXT]",
                "description": "Create a VEVENT (If-None-Match: *).",
            },
            "update": {
                "usage": "agents-calendar update --href HREF --etag ETAG [--summary TEXT] [--dtstart ISO] [--dtend ISO] [--location TEXT] [--description TEXT]",
                "description": "Replace a VEVENT (If-Match etag).",
            },
            "delete": {
                "usage": "agents-calendar delete --href HREF --etag ETAG",
                "description": "Delete a VEVENT (If-Match etag).",
            },
            "serve": {
                "usage": "agents-calendar serve",
                "description": "Start FastMCP stdio server.",
            },
        },
        "flags": ["--help-json"],
        "env": ["CALDAV_URL", "CALDAV_USERNAME", "CALDAV_PASSWORD"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agents-calendar",
        description="CalDAV calendar feeler. Credentials stay in env.",
    )
    parser.add_argument("--help-json", action="store_true", help="Emit machine-readable CLI spec as JSON.")
    parser.add_argument("-v", "--version", action="version", version=f"agents-calendar {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("calendars", help="List calendar collections")
    sub.add_parser("serve", help="Start FastMCP stdio server")

    list_p = sub.add_parser("list", help="List events in a time range")
    list_p.add_argument("--from", dest="start", default="")
    list_p.add_argument("--to", dest="end", default="")
    list_p.add_argument("start_pos", nargs="?", default="")
    list_p.add_argument("end_pos", nargs="?", default="")

    add_p = sub.add_parser("add", help="Create an event")
    add_p.add_argument("--summary", default="")
    add_p.add_argument("--dtstart", default="")
    add_p.add_argument("--dtend", default="")
    add_p.add_argument("--location", default="")
    add_p.add_argument("--description", default="")
    add_p.add_argument("summary_pos", nargs="?", default="")
    add_p.add_argument("dtstart_pos", nargs="?", default="")
    add_p.add_argument("dtend_pos", nargs="?", default="")

    upd_p = sub.add_parser("update", help="Update an event")
    upd_p.add_argument("--href", default="")
    upd_p.add_argument("--etag", default="")
    upd_p.add_argument("--summary", default="")
    upd_p.add_argument("--dtstart", default="")
    upd_p.add_argument("--dtend", default="")
    upd_p.add_argument("--location", default=None)
    upd_p.add_argument("--description", default=None)
    upd_p.add_argument("href_pos", nargs="?", default="")
    upd_p.add_argument("etag_pos", nargs="?", default="")

    del_p = sub.add_parser("delete", help="Delete an event")
    del_p.add_argument("--href", default="")
    del_p.add_argument("--etag", default="")
    del_p.add_argument("href_pos", nargs="?", default="")
    del_p.add_argument("etag_pos", nargs="?", default="")
    return parser


def _dump(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _client() -> CaldavClient:
    return CaldavClient(load_settings())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.help_json:
        print(json.dumps(help_json(), indent=2))
        return 0
    if args.command == "serve":
        from .mcp_server import mcp

        mcp.run()
        return 0
    try:
        if args.command == "calendars":
            _dump(_client().calendars())
            return 0
        if args.command == "list":
            start = args.start or args.start_pos
            end = args.end or args.end_pos
            if not start or not end:
                print("list needs --from and --to (ISO)", file=sys.stderr)
                return 2
            _dump(_client().list_events(start, end))
            return 0
        if args.command == "add":
            summary = args.summary or args.summary_pos
            dtstart = args.dtstart or args.dtstart_pos
            dtend = args.dtend or args.dtend_pos
            if not summary or not dtstart or not dtend:
                print("add needs --summary --dtstart --dtend", file=sys.stderr)
                return 2
            _dump(
                _client().add_event(
                    summary=summary,
                    dtstart=dtstart,
                    dtend=dtend,
                    location=args.location,
                    description=args.description,
                )
            )
            return 0
        if args.command == "update":
            href = args.href or args.href_pos
            etag = args.etag or args.etag_pos
            if not href or not etag:
                print("update needs --href and --etag", file=sys.stderr)
                return 2
            _dump(
                _client().update_event(
                    href,
                    etag,
                    summary=args.summary or None,
                    dtstart=args.dtstart or None,
                    dtend=args.dtend or None,
                    location=args.location,
                    description=args.description,
                )
            )
            return 0
        if args.command == "delete":
            href = args.href or args.href_pos
            etag = args.etag or args.etag_pos
            if not href or not etag:
                print("delete needs --href and --etag", file=sys.stderr)
                return 2
            _dump(_client().delete_event(href, etag))
            return 0
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except PreconditionFailed as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (CaldavError, IcsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.print_help()
    return 0
