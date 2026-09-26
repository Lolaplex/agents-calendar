# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Lolaplex/agents-calendar/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/Lolaplex/agents-calendar/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/Lolaplex/agents-calendar/releases/tag/v0.0.1

