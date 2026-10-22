# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Naive datetimes are wall times in the resolved IANA zone. A value such as `2026-10-22T10:00:00` is 10:00 in that zone, including the daylight-saving offset for that date. It is not a UTC timestamp and it is not stored as an all-day event.
- Spring-forward gaps and fall-back overlaps are rejected unless the input carries an explicit UTC offset.
- `TZID` on incoming events is honored. An IANA id uses `zoneinfo`. Any other id is resolved from the embedded `VTIMEZONE`. Floating times use the resolved zone. `Z` and numeric offsets stay absolute instants.
- All-day events are read and written as `VALUE=DATE` with an exclusive `DTEND`. Returned `dtstart` / `dtend` are civil dates and `all_day` is true.
- Updates keep unrelated properties (`RRULE`, `EXDATE`, `RDATE`, `VALARM`, `ATTENDEE`, `UID`, `X-` properties), bump `SEQUENCE`, and refresh `DTSTAMP` and `LAST-MODIFIED`.

### Added
- Timed events are written with `DTSTART`/`DTEND;TZID=<zone>` and a `VTIMEZONE` derived from the IANA time zone database. Weekly recurrence expanded by the CalDAV server therefore stays on the same wall clock across DST. An ambiguous wall time is stored as UTC so the fall-back instant is not lost.
- Zone resolution order: explicit argument, then `CALDAV_TIMEZONE` (or `timezone` in the credentials file), then the collection's CalDAV `calendar-timezone` when its id is an IANA name, then the host zone (`TZ` or the OS database), then `UTC`.
- `tzdata` is a dependency on every platform so `zoneinfo` has IANA data when the operating system does not.

### Changed
- All-day `dtstart` / `dtend` / `dtstart_local` / `dtend_local` are `YYYY-MM-DD` dates. They are no longer UTC midnight timestamps.
- A date-only time-range bound is 00:00 in the resolved zone, then converted to UTC.
- There is no hard-coded regional default. When the host zone cannot be determined the fallback is `UTC`.
- Changing only `dtstart` or only `dtend` keeps the other instant when the span stays positive. If that edit would reverse the span, the previous duration is kept.

## [0.1.2] - 2026-10-21

### Fixed
- Declare `tzdata; sys_platform == 'win32'` as a package dependency so Python's standard library `zoneinfo` has the IANA time zone database available on Windows installations where OS-level tzdata is absent.

## [0.1.1] - 2026-10-10

### Added
- Fully timezone and daylight saving time (DST / Zeitumstellung) sensitive handling using Python standard library `zoneinfo`.
- Naive datetime inputs (e.g. `2026-11-29T16:00:00`) are deterministically localized in `CALDAV_TIMEZONE` (or auto-detected system timezone, e.g. `Europe/Berlin`) and converted to UTC (`2026-11-29T15:00:00Z`).
- Rich event return fields across all endpoints (`calendar_list`, `calendar_get`, `calendar_add`, `calendar_update`): `dtstart` (UTC), `dtstart_local` (with timezone offset), `dtend`, `dtend_local`, `timezone`, `all_day`, and `calendar`.
- `calendar_get` MCP tool and `agents-calendar get` CLI command to retrieve single events by href.
- Property parameter parsing for `DTSTART;TZID=...` and `DTSTART;VALUE=DATE:...` in iCalendar payloads.
- `all_day` support for full-day events.

## [0.1.0] - 2026-10-06

### Added
- `--calendar NAME` on `list` and `add`, and `calendar` on the `calendar_list` / `calendar_add` MCP tools, pick a collection by display name or URL. `CALDAV_CALENDAR` (or `calendar` in `calendar.json`) sets the default collection for `add`. An unknown name fails with the list of available calendars.
- CLI (and MCP, when present) check PyPI at most once per day for a newer release and print one stderr / tool-response line (`uv tool upgrade …`). Disabled with `AGENTS_NO_UPDATE_CHECK=1` or when `CI` is set; offline/timeout stays silent.

## [0.0.3] - 2026-09-26

### Added
- ABI contract in `abi/` for credentials, the five MCP tools, and the CLI.

### Changed
- README matches the live CLI and the five MCP tools. `init` is the alias of `sync --init`. Bare `agents-calendar` prints help.

## [0.0.2] - 2026-09-26

### Changed
- Refined README with full benchmark specification (architecture diagram, MCP tools table, CLI reference, and quickstarts).
- Cleaned production environment setup notes in documentation.

### Fixed
- `add` writes the event into a VEVENT collection. A CalDAV home or principal URL is no longer used as the PUT target, and reminder collections that only allow VTODO are skipped. HTTP errors include a short response snippet.

## [0.0.1] - 2026-09-20

### Added
- CalDAV feeler: list/add/update/delete events and list calendars via CLI and MCP.
- Stdlib HTTP client (Basic auth). Recurrence expanded by the server time-range query.
- Host MCP nest via `sync --init` / `init`: merge `mcpServers.agents-calendar` into Cursor, Claude, Antigravity/Gemini, Zed, Codex, and VS Code Cline/Roo configs without clobbering other servers.
- Host credentials file `~/.agents/calendar.json` (mode 0600) with process env `CALDAV_*` override.

### Changed
- CI runs only on pull requests to `main`.
- README now documents install, the real CLI (`calendars` / `list` / `add` / `update` / `delete` / `serve`), MCP tools, and verify commands.

### Fixed
- Discover `calendar-home-set` when `CALDAV_URL` is a host or principal (iCloud) and query each calendar.
- Parse all-day iCalendar DATE values (`YYYYMMDD`) as UTC midnight.

[Unreleased]: https://github.com/Lolaplex/agents-calendar/compare/v0.1.2...HEAD
[0.1.1]: https://github.com/Lolaplex/agents-calendar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Lolaplex/agents-calendar/compare/v0.0.3...v0.1.0
[0.0.3]: https://github.com/Lolaplex/agents-calendar/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/Lolaplex/agents-calendar/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/Lolaplex/agents-calendar/releases/tag/v0.0.1

