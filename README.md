# agents-calendar

CalDAV feeler for agents. CLI and MCP. Events only (v0). Python stdlib HTTP plus `mcp`. No `caldav` / `icalendar` libraries. No CardDAV. No WebDAV files. No RRULE parser — the server expands recurrence via time-range.

Cursor (MCP) and Klanker (Cordis `call_job`) share this CLI. Credentials live in env, never in chat, traces, or markdown memory. The CLI never prints the password.

## Install

```bash
python -m pip install -e .
```

Python 3.10+. Depends on `mcp`.

## Commands

Machine catalog: `python -m agents_calendar --help-json` (do not scrape `--help`).

```bash
export CALDAV_URL="https://example/dav/calendars/user/calendar/"
export CALDAV_USERNAME="user"
export CALDAV_PASSWORD="app-password"

python -m agents_calendar calendars
python -m agents_calendar list --from 2026-09-13T00:00:00Z --to 2026-09-14T00:00:00Z
<<<<<<< HEAD
python -m agents_calendar add --summary "Exam" --dtstart 2026-09-14T08:00:00Z --dtend 2026-09-14T10:00:00Z
python -m agents_calendar update --href <href> --etag <etag> --summary "Exam (moved)"
python -m agents_calendar delete --href <href> --etag <etag>
python -m agents_calendar serve
python -m agents_calendar sync --init
```

| Command | Purpose |
|---------|---------|
| `calendars` | List collections under `CALDAV_URL` |
| `list --from ISO --to ISO` | VEVENTs in the range. Server expands recurrence |
| `add --summary --dtstart --dtend [--location] [--description]` | Create (`If-None-Match: *`) |
| `update --href --etag […]` | Replace (`If-Match`). Missing etag is a hard error |
| `delete --href --etag` | Delete (`If-Match`). Missing etag is a hard error |
| `serve` | FastMCP stdio |
| `sync --init` / `init` | Merge `mcpServers.agents-calendar` into host MCP configs |

MCP: `sync --init` (or `init`) merges `mcpServers.agents-calendar` into installed host configs (Cursor, Claude, Antigravity/Gemini, Zed, …). Merge by key only; other servers stay. Manual copy of `mcp.json.example` still works. Never writes `CALDAV_PASSWORD`.

## MCP

Copy `mcp.json.example` into the host MCP config. Do not auto-merge `~/.cursor/mcp.json`. Tools mirror the CLI: `calendar_calendars`, `calendar_list`, `calendar_add`, `calendar_update`, `calendar_delete`. Password never in responses.

## Env

| Variable | Role |
|----------|------|
| `CALDAV_URL` | Calendar collection URL |
| `CALDAV_USERNAME` | Basic auth user |
| `CALDAV_PASSWORD` | App password. Never print it |

## Constraints

- Harness shells this CLI. It does not import this package.
- Write uses `If-Match` / `If-None-Match`.

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## License

MIT. See [LICENSE](LICENSE).
