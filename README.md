<h1 align="center">agents-calendar</h1>

<p align="center">
  <a href="https://github.com/Lolaplex/agents-calendar/releases"><img src="https://img.shields.io/badge/version-0.1.1-blue.svg?style=flat-square" alt="Version 0.1.1"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-Standard-orange.svg?style=flat-square" alt="MCP"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://pypi.org/project/agents-calendar/"><img src="https://img.shields.io/pypi/v/agents-calendar.svg?style=flat-square" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <strong>CalDAV feeler for agents (CLI + MCP).</strong><br>
  Stdlib HTTP. The server expands recurrence. Passwords stay on the host.
</p>

## Quickstart

```bash
pip install agents-calendar && agents-calendar sync --init
```

Merges MCP into host configs. Prints where credentials go. Does not write secrets into `mcp.json`. `init` is the same command.

> [!TIP]
> **🤖 Agent-Driven Setup:**
> Give your coding agent **this repo** (clone or URL), then tell it to **"install and set up agents-calendar."**

Source checkouts can also be installed and managed with [vand](https://github.com/Lolaplex/vand).

---

## What it does

List calendars, list events in a time range, add, update, delete. Recurrence rules stay on the CalDAV server (`time-range` report). Writes send `If-None-Match: *` on create and `If-Match` on update and delete, so a stale etag does not clobber.

The password is never printed, logged, or returned by a tool.

---

## Credentials

Highest priority first:

1. Process env: `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`, optional `CALDAV_CALENDAR`
2. `~/.agents/calendar.json` (mode `0600`)
3. `~/.agents/.env` keys `CALDAV_*`

```json
{
  "url": "https://example.com/dav/calendars/user/calendar/",
  "username": "user",
  "password": "app-password",
  "calendar": "Work"
}
```

`calendar` (or `CALDAV_CALENDAR`) is optional: the collection, by display name or URL, that `add` writes to. `list` searches every collection unless `--calendar` names one. Both commands and the MCP tools accept `calendar` per call.

CLI and MCP both read this file, so a desktop host does not need the password in its MCP config. A URL that is only a host or principal is resolved through `calendar-home-set`. `add` writes into a VEVENT collection, not a reminder collection.

---

## Where it runs

**Floor:** any MCP client or a terminal. `python -m agents_calendar serve` is enough. No skills are installed.

| Layer | What you get | Who |
| --- | --- | --- |
| **CLI + MCP** | The five tools below, or the same verbs on the CLI | Any MCP host / any shell |
| **Autowire** | `sync --init` merges `agents-calendar` when the host config directory already exists, and ensures `~/.cursor/mcp.json` | Cursor, Claude Desktop, Zed (`context_servers`), Antigravity / Gemini, Windsurf, Codex, Roo, Cline |

**MCP without autowire:** point the host at `python -m agents_calendar serve`.

---

## MCP tools

Primary surface. They mirror the CLI. Password never appears in the JSON.

| Tool | What it does |
| :--- | :--- |
| `calendar_calendars` | Collections under the configured URL |
| `calendar_list` | VEVENTs between ISO `start` and `end`. Returns UTC and local times |
| `calendar_get` | Get a single VEVENT by `href` with UTC and local times |
| `calendar_add` | Create. `If-None-Match` so an existing UID is not overwritten |
| `calendar_update` | Replace. `href` and `etag` come from `calendar_list` or `calendar_get` |
| `calendar_delete` | Delete. Same `href` + `etag` pair |

Six tools. Timezone and daylight saving time (DST) shifts are handled deterministically via Python `zoneinfo`.

---

## CLI

Machine-readable catalog: `python -m agents_calendar --help-json` (do not scrape `--help`).

| Command | Purpose |
| --- | --- |
| `agents-calendar sync --init` | Merge MCP. Alias: `agents-calendar init` |
| `agents-calendar calendars` | List collections |
| `agents-calendar list --from <ISO> --to <ISO>` | Events in that range with local & UTC times |
| `agents-calendar get --href <href>` | Get event details by href |
| `agents-calendar add --summary "…" --dtstart <ISO> --dtend <ISO>` | Create. Optional `--location`, `--description`, `--timezone`, `--all-day` |
| `agents-calendar update --href <href> --etag <etag> …` | Replace fields you pass |
| `agents-calendar delete --href <href> --etag <etag>` | Delete |
| `agents-calendar serve` | stdio MCP. Not the default |

No subcommand prints help.

---

## ABI

Contract in [`abi/`](abi/):

- [`WHY.md`](abi/WHY.md) — server-side recurrence and etags
- [`LAYOUT.md`](abi/LAYOUT.md) — credential file
- [`MCP.md`](abi/MCP.md) — five tools
- [`CLI.md`](abi/CLI.md) — the same verbs, plus `init`

---

## Tests

```bash
python -m unittest discover tests
```

---

## License

MIT. See [LICENSE](LICENSE).
