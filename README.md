# agents-calendar

<p align="left">
  <a href="https://github.com/Lolaplex/agents-calendar/releases"><img src="https://img.shields.io/badge/version-0.0.2-blue.svg?style=flat-square" alt="Version 0.0.2"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-Standard-orange.svg?style=flat-square" alt="MCP"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://pypi.org/project/agents-calendar/"><img src="https://img.shields.io/pypi/v/agents-calendar.svg?style=flat-square" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License"></a>
</p>

**CalDAV calendar feeler for AI agents (CLI + MCP).**  
Python stdlib HTTP plus `mcp`. Zero heavy external dependencies (`caldav`, `icalendar`, or heavy XML engines). Shared across **Cursor**, **Claude Code**, **Antigravity**, and **Zed**.

---

## Quickstart

### 1-Step Setup

```bash
pip install agents-calendar && agents-calendar sync --init
```

Scaffolds host MCP configuration and prints credential setup instructions.

### 2. Agent-Driven Setup (Zero Friction)

> [!TIP]
> **🤖 Agent-Driven Setup (Zero Friction):**  
> Simply tell your coding agent: **"Install and set up agents-calendar for me."**  
> The agent installs the package, runs `agents-calendar sync --init`, and sets up the credentials file.

*Source checkouts can also be installed and managed using [vand](https://github.com/Lolaplex/vand).*

---

## Why `agents-calendar`?

Most calendar libraries pull in complex dependency trees with slow date/time parsers and bloated XML engines.

**`agents-calendar` applies the Lolaplex philosophy:**
- **Zero Heavy Dependencies**: Pure Python standard library HTTP + lightweight FastMCP stdio interface.
- **Server-Side Recurrence Expansion**: Lets the CalDAV server expand recurrence rules (RRULE) via time-range queries instead of running local client-side recurrence calculation engines.
- **Safe Concurrency & Idempotency**: Enforces `If-Match` and `If-None-Match` HTTP headers with ETags on event additions, updates, and deletions to prevent race conditions and unintentional overwrites.
- **Strict Credential Hygiene**: Keeps passwords in a locked local host file (`~/.agents/calendar.json`, mode 0600) or environment variables. Passwords are never echoed, printed to stdout, logged to traces, or committed to git.

---

## Architecture & Flow

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                     CODING AGENT / IDE                      │
 │    Cursor · Antigravity · Claude Code · Custom Agents       │
 └──────────────────────────────┬──────────────────────────────┘
                                │  MCP Tools / CLI Verbs
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                      AGENTS-CALENDAR                        │
 │    FastMCP Server · Stdlib HTTP Client · ETag Validator     │
 └──────────────┬───────────────────────────────┬──────────────┘
                │                               │
                ▼                               ▼
 ┌─────────────────────────────┐ ┌─────────────────────────────┐
 │       LOCAL HOST FILE       │ │     REMOTE CALDAV SERVER    │
 │   ~/.agents/calendar.json   │ │  Nextcloud · iCloud · Baïkal│
 │   (mode 0600, secrets safe) │ │  Time-range event expansion │
 └─────────────────────────────┘ └─────────────────────────────┘
```

---

## Configuration & Credentials

Write your credentials into `~/.agents/calendar.json` (mode `0600`, never commit):

```json
{
  "url": "https://example.com/dav/calendars/user/calendar/",
  "username": "user",
  "password": "app-password"
}
```

CLI and MCP both read this file, ensuring desktop MCP hosts work seamlessly without requiring environment variables in GUI sessions.

### Load Order (highest priority wins):
1. Process environment variables: `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`
2. Local credentials file: `~/.agents/calendar.json`
3. Host environment file: `~/.agents/.env` with `CALDAV_*` keys

In production or Docker containers, set environment variables directly. `sync --init` never writes secrets into `mcp.json`.

---

## CLI Reference

Machine catalog: `python -m agents_calendar --help-json`

| Command | Purpose |
|---------|---------|
| `agents-calendar sync --init` | Merges MCP configuration into installed IDEs without clobbering other servers |
| `agents-calendar calendars` | Discovers and lists all calendar collections under `CALDAV_URL` |
| `agents-calendar list --from <ISO> --to <ISO>` | Lists events between ISO-8601 start and end timestamps |
| `agents-calendar add --summary "..." --dtstart <ISO> --dtend <ISO>` | Creates a new calendar event with `If-None-Match` protection |
| `agents-calendar update --href <href> --etag <etag> --summary "..."` | Updates an existing event using `If-Match` validation |
| `agents-calendar delete --href <href> --etag <etag>` | Deletes an event using `If-Match` validation |
| `agents-calendar serve` | Runs the FastMCP stdio server (default) |

---

## MCP Tools Reference

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `calendar_calendars` | *None* | Lists all calendar collections available under the configured URL. |
| `calendar_list` | `start`, `end` | Lists VEVENTs between ISO timestamps. Recurrence is expanded by the server. |
| `calendar_add` | `summary`, `dtstart`, `dtend`, `location` (opt), `description` (opt) | Creates a new calendar event. Prevents UID collisions via `If-None-Match`. |
| `calendar_update` | `href`, `etag`, `summary` (opt), `dtstart` (opt), `dtend` (opt), `location` (opt), `description` (opt) | Updates an existing event. Validates against stale edits via `etag`. |
| `calendar_delete` | `href`, `etag` | Deletes an event by its href and etag. |

---

## Testing & Verification

Run the test suite:

```bash
python -m unittest discover tests
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
