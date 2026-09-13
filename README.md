# agents-calendar

CalDAV calendar feeler for AI agents. CLI and MCP. Python stdlib HTTP plus `mcp`. No `caldav` / `icalendar` libraries.

Cursor (MCP) and Klanker (Cordis `call_job`) share this CLI. Credentials live in env, never in chat.

```bash
pip install -e .
export CALDAV_URL="https://example/dav/calendars/user/calendar/"
export CALDAV_USERNAME="user"
export CALDAV_PASSWORD="app-password"

python -m agents_calendar --help-json
python -m agents_calendar list --from 2026-09-13T00:00:00Z --to 2026-09-14T00:00:00Z
```

MCP: copy `mcp.json.example` into the host MCP config. Do not auto-merge `~/.cursor/mcp.json`.

Tests: `python -m unittest discover tests`
