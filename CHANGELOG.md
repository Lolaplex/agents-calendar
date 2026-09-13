# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Host MCP nest via `sync --init` / `init`: merge `mcpServers.agents-calendar` into Cursor, Claude, Antigravity/Gemini, Zed, Codex, and VS Code Cline/Roo configs without clobbering other servers.
- Host credentials file `~/.agents/calendar.json` (mode 0600). CLI and MCP share it so Cursor MCP works without mcp.json `env`. Process env `CALDAV_*` still wins (Coolify/VPS path); `sync --init` does not write secrets into mcp.json.

### Changed
- CI runs only on pull requests to `main`.
- README now documents install, the real CLI (`calendars` / `list` / `add` / `update` / `delete` / `serve`), MCP tools, and the verify command.

### Deprecated

### Removed
- GitHub Release is no longer cut automatically on `v*.*.*` tags (manual `gh release create` from CHANGELOG instead).

### Fixed
- Discover `calendar-home-set` when `CALDAV_URL` is a host or principal (iCloud) and query each calendar.
- Parse all-day iCalendar DATE values (`YYYYMMDD`) as UTC midnight.

### Security

## [0.0.1] - 2026-09-13

### Added
- CalDAV feeler: list/add/update/delete events and list calendars via CLI and MCP.
- Stdlib HTTP client (Basic auth). Recurrence expanded by the server time-range query.

[Unreleased]: https://github.com/Lolaplex/agents-calendar/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/Lolaplex/agents-calendar/releases/tag/v0.0.1
