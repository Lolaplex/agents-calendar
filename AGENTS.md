# agents-calendar

CalDAV feeler. CLI + MCP. Events only (v0). No CardDAV. No WebDAV files. No RRULE parser — server expands via time-range.

## Commands

```bash
python -m agents_calendar --help-json
python -m agents_calendar sync --init
python -m agents_calendar init
python -m agents_calendar calendars
python -m agents_calendar list --from 2026-09-13T00:00:00Z --to 2026-09-14T00:00:00Z [--calendar "Work"] [--timezone "Europe/Berlin"]
python -m agents_calendar get --href <href> [--timezone "Europe/Berlin"]
python -m agents_calendar add --summary "Exam" --dtstart 2026-09-14T08:00:00Z --dtend 2026-09-14T10:00:00Z [--calendar "Work"] [--timezone "Europe/Berlin"]
python -m agents_calendar update --href <href> --etag <etag> --summary "Exam (moved)" [--timezone "Europe/Berlin"]
python -m agents_calendar delete --href <href> --etag <etag>
python -m agents_calendar serve
```

`sync --init` / `init` merge `mcpServers.agents-calendar` into host MCP configs (Cursor, Claude, Antigravity/Gemini, Zed, Codex, VS Code Cline/Roo, Windsurf). Merge by key only; other servers stay. Cursor mkdir if `~/.cursor` missing. Never auto-write secrets. Stdout mentions `~/.agents/calendar.json`.

## Timezones & Deterministic DST

`zoneinfo` (IANA tz database; the `tzdata` package supplies it when the OS does not). No hand-rolled offsets.

Resolution order for the zone that interprets naive input and formats local output:

1. Explicit `timezone` argument (CLI `--timezone`, MCP `timezone`).
2. Configured zone: `CALDAV_TIMEZONE`, else `AGENTS_TIMEZONE`, else `timezone` in `calendar.json` / `CALDAV_TIMEZONE` in `~/.agents/.env`.
3. The collection's CalDAV `calendar-timezone` (or `calendar-timezone-id`) when that id is an IANA name.
4. Host zone: `TZ`, else the OS zone database.
5. `UTC` when the host zone cannot be determined.

- Naive input (`2026-11-29T16:00:00`, `2026-11-29 16:00`, `20261129T160000`) is wall time in that zone. The offset is the IANA offset for that date, so DST transitions are per date.
- `Z` or a numeric offset is an absolute instant and is kept. A fall-back overlap stored with `TZID` cannot tell the two instants apart, so those instants are written as UTC.
- Spring-forward gaps and fall-back overlaps without an explicit offset raise `IcsError`. Do not guess.
- Timed writes use `DTSTART`/`DTEND;TZID=<zone>` plus a `VTIMEZONE` built from the IANA data. The server expands `RRULE` in that zone, so a weekly wall time stays put across DST. This package still does not parse `RRULE`.
- All-day values (`all_day` or `YYYY-MM-DD`) are `VALUE=DATE`. `DTEND` is exclusive. The same date for start and end means one civil day.
- Read path: IANA `TZID` via `zoneinfo`; any other `TZID` via `VTIMEZONE`; `Z` / numeric offsets as instants; floating times in the resolved zone; `VALUE=DATE` as all-day.
- Returned event dictionaries from `list_events`, `get_event`, `add_event`, and `update_event` include:
  - `dtstart`: UTC ISO timestamp, or `YYYY-MM-DD` when `all_day`
  - `dtstart_local`: local ISO timestamp with a numeric offset (e.g. `2026-11-29T16:00:00+01:00`), or the civil date when `all_day`
  - `dtend` and `dtend_local` (all-day `dtend` is the exclusive date)
  - `timezone`: IANA name used for the local fields
  - `all_day`: boolean
  - `calendar`: calendar collection name
- Updates preserve `RRULE`, `EXDATE`, `RDATE`, `VALARM`, `ATTENDEE`, `UID`, and `X-` properties. `SEQUENCE` increments. `DTSTAMP` and `LAST-MODIFIED` are refreshed. Changing only one of `dtstart` / `dtend` keeps the other instant when the span stays positive; if the edit would reverse the span, the previous duration is kept.

## Credentials & Config

Host file `~/.agents/calendar.json` (mode `0600`): keys `url`, `username`, `password`, optional `calendar`, optional `timezone` (e.g. `"Europe/Berlin"`). CLI and MCP share it.

Load order (highest wins): process env `CALDAV_URL` / `CALDAV_USERNAME` / `CALDAV_PASSWORD` / `CALDAV_CALENDAR` / `CALDAV_TIMEZONE`, else the JSON file, else `~/.agents/.env` with `CALDAV_*`.

- Desktop: `~/.agents/calendar.json` (0600). Cursor MCP: file primary; mcp.json `env` optional.
- Production / Docker: Environment variables `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`. Never git, never chat.

Never print the password. Never store it in traces, chat, markdown memory, or mcp.json.

Write uses `If-Match` / `If-None-Match`. Missing etag on update/delete is a hard error.

Harness shells this CLI. It does not import this package.
