# MCP surface

Server: `python -m agents_calendar serve` (FastMCP). Tool results are JSON. Errors are `{"error": "..."}`. The password is not in the JSON.

### `calendar_calendars()`

Collections under the configured URL.

### `calendar_list(start, end, calendar="", timezone="")`

`VEVENT`s between two ISO-8601 timestamps. The server expands recurrence. Optional `calendar` collection name or URL. Optional `timezone` (default: `CALDAV_TIMEZONE` or system local, e.g. `Europe/Berlin`).
Returned events include:
- `dtstart`: UTC ISO-8601 timestamp (`YYYY-MM-DDTHH:MM:SSZ`)
- `dtstart_local`: local ISO timestamp with timezone offset (e.g. `2026-11-29T16:00:00+01:00`) or date
- `dtend`: UTC ISO-8601 timestamp
- `dtend_local`: local ISO timestamp with timezone offset or date
- `timezone`: timezone name used for local conversion
- `all_day`: boolean flag for all-day events
- `calendar`: calendar collection name
- `href` and `etag`: required for update and delete
- `summary`, `location`, `description`, `status`, `uid`

### `calendar_get(href, timezone="")`

Fetch a single event by its href. Returns the rich event object with both UTC and local times.

### `calendar_add(summary, dtstart, dtend, calendar="", location="", description="", timezone="", all_day=False, status="")`

Create. `If-None-Match: *`.
`dtstart` and `dtend` accept ISO strings or dates. Naive timestamps are deterministically converted to UTC in `timezone` (default: configured `CALDAV_TIMEZONE` or `Europe/Berlin`), accurately handling daylight saving time (DST) shifts. Returns the full created event dictionary.

### `calendar_update(href, etag, summary="", dtstart="", dtend="", location="", description="", timezone="", all_day=None, status="")`

Replace. `If-Match` is the etag from `calendar_list` or `calendar_get`. Empty strings leave that field unchanged.

### `calendar_delete(href, etag)`

Delete. `If-Match` required.
