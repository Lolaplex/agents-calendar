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

- `agents-calendar` is fully timezone and DST (daylight saving time / Zeitumstellung) sensitive.
- Naive datetime inputs (e.g. `2026-11-29T16:00:00`) are deterministically localized in `CALDAV_TIMEZONE` (or auto-detected system timezone, e.g. `Europe/Berlin`) using Python `zoneinfo` and converted to UTC (`2026-11-29T15:00:00Z`).
- Returned event dictionaries from `list_events`, `get_event`, `add_event`, and `update_event` include:
  - `dtstart`: UTC ISO timestamp
  - `dtstart_local`: local ISO timestamp with timezone offset (e.g. `2026-11-29T16:00:00+01:00`) or date
  - `dtend` and `dtend_local`
  - `timezone`: target timezone name
  - `all_day`: boolean
  - `calendar`: calendar collection name

## Credentials & Config

Host file `~/.agents/calendar.json` (mode `0600`): keys `url`, `username`, `password`, optional `calendar`, optional `timezone` (e.g. `"Europe/Berlin"`). CLI and MCP share it.

Load order (highest wins): process env `CALDAV_URL` / `CALDAV_USERNAME` / `CALDAV_PASSWORD` / `CALDAV_CALENDAR` / `CALDAV_TIMEZONE`, else the JSON file, else `~/.agents/.env` with `CALDAV_*`.

- Desktop: `~/.agents/calendar.json` (0600). Cursor MCP: file primary; mcp.json `env` optional.
- Production / Docker: Environment variables `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`. Never git, never chat.

Never print the password. Never store it in traces, chat, markdown memory, or mcp.json.

Write uses `If-Match` / `If-None-Match`. Missing etag on update/delete is a hard error.

Harness shells this CLI. It does not import this package.
