# CLI

Installed command: `agents-calendar`. No subcommand prints help. It does not start the MCP server.

- `agents-calendar sync --init` — merge `mcpServers.agents-calendar` into host configs whose directories exist, and ensure `~/.cursor/mcp.json`. Prints the credentials path. Does not write secrets. Alias: `agents-calendar init`.
- `agents-calendar calendars` — JSON list of collections.
- `agents-calendar list --from ISO --to ISO` — JSON events. Both bounds required.
- `agents-calendar add --summary TEXT --dtstart ISO --dtend ISO [--location TEXT] [--description TEXT]` — create.
- `agents-calendar update --href HREF --etag ETAG [--summary TEXT] [--dtstart ISO] [--dtend ISO] [--location TEXT] [--description TEXT]` — replace. `href` and `etag` required.
- `agents-calendar delete --href HREF --etag ETAG` — delete.
- `agents-calendar serve` — FastMCP stdio.

Exit 2: missing config or missing required flags. Exit 3: precondition failed (etag). Exit 1: other CalDAV or iCalendar error.

`python -m agents_calendar --help-json` prints the machine catalog.
