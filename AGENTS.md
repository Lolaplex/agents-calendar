# agents-calendar

CalDAV feeler. CLI + MCP. Events only (v0). No CardDAV. No WebDAV files. No RRULE parser — server expands via time-range.

## Commands

```bash
python -m agents_calendar --help-json
python -m agents_calendar sync --init
python -m agents_calendar init
python -m agents_calendar calendars
python -m agents_calendar list --from 2026-09-13T00:00:00Z --to 2026-09-14T00:00:00Z
python -m agents_calendar add --summary "Exam" --dtstart 2026-09-14T08:00:00Z --dtend 2026-09-14T10:00:00Z
python -m agents_calendar update --href <href> --etag <etag> --summary "Exam (moved)"
python -m agents_calendar delete --href <href> --etag <etag>
python -m agents_calendar serve
```

`sync --init` / `init` merge `mcpServers.agents-calendar` into host MCP configs (Cursor, Claude, Antigravity/Gemini, Zed, Codex, VS Code Cline/Roo, Windsurf). Merge by key only; other servers stay. Cursor mkdir if `~/.cursor` missing. Never auto-write secrets. Stdout mentions `~/.agents/calendar.json`.

## Credentials

Host file `~/.agents/calendar.json` (mode `0600`): keys `url`, `username`, `password`. CLI and MCP share it. Cursor GUI does not inherit a random PowerShell session.

Load order (highest wins): process env `CALDAV_URL` / `CALDAV_USERNAME` / `CALDAV_PASSWORD`, else the JSON file, else `~/.agents/.env` with `CALDAV_*`. Optional mcp.json `env` still works (process env wins).

- Desktop: `~/.agents/calendar.json` (0600). Cursor MCP: file primary; mcp.json `env` optional.
- VPS / `klanker serve`: Coolify env `CALDAV_*`. Never git, never chat.

Never print the password. Never store it in traces, chat, markdown memory, or mcp.json.

Write uses `If-Match` / `If-None-Match`. Missing etag on update/delete is a hard error.

Harness shells this CLI. It does not import this package.
