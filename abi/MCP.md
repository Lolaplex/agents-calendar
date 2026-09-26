# MCP surface

Server: `python -m agents_calendar serve` (FastMCP). Tool results are JSON. Errors are `{"error": "..."}`. The password is not in the JSON.

### `calendar_calendars()`

Collections under the configured URL.

### `calendar_list(start, end)`

`VEVENT`s between two ISO-8601 timestamps. The server expands recurrence. Each item includes the `href` and `etag` required for update and delete.

### `calendar_add(summary, dtstart, dtend, location="", description="")`

Create. `If-None-Match: *`.

### `calendar_update(href, etag, summary="", dtstart="", dtend="", location="", description="")`

Replace. `If-Match` is the etag from `calendar_list`. Empty strings leave that field unchanged.

### `calendar_delete(href, etag)`

Delete. `If-Match` required.
