# agents-calendar

CalDAV calendar feeler for AI agents. CLI and MCP. Python stdlib HTTP plus `mcp`. No `caldav` / `icalendar` libraries.

Cursor (MCP) and Klanker (Cordis `call_job`) share this CLI.

```bash
pip install -e .
python -m agents_calendar --help-json
python -m agents_calendar list --from 2026-09-13T00:00:00Z --to 2026-09-14T00:00:00Z
python -m agents_calendar sync --init
```

MCP: `sync --init` (or `init`) merges `mcpServers.agents-calendar` into installed host configs. Merge by key only; other servers stay. Manual copy of `mcp.json.example` still works.

## Credentials

Write `~/.agents/calendar.json` (mode `0600`, never commit). Example: `calendar.json.example`.

```json
{
  "url": "https://example/dav/calendars/user/calendar/",
  "username": "user",
  "password": "app-password"
}
```

CLI and MCP both read this file, so Cursor MCP works without `mcp.json` `env` and without launching Cursor from a shell.

Load order (highest wins): process env `CALDAV_URL` / `CALDAV_USERNAME` / `CALDAV_PASSWORD`, else the JSON file, else `~/.agents/.env` with the same `CALDAV_*` keys. Optional `mcp.json` `"env"` still works because process env wins. `sync --init` never writes secrets into mcp.json.

Where to type the three values:

- Desktop / Cursor MCP: `~/.agents/calendar.json` (mode `0600`). File is primary so Cursor GUI works without inheriting a PowerShell session. `mcp.json` `env` is optional.
- VPS / Klanker serve / Coolify container: Coolify env `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`. Never git, never chat. Process env wins over the host file.

Tests: `python -m unittest discover tests`
