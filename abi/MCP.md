# MCP surface

Server: `python -m agents_calendar serve` (FastMCP). Tool results are JSON. Errors are `{"error": "..."}`. The password is not in the JSON.

### `calendar_calendars()`

Collections under the configured URL.

### `calendar_list(start, end, calendar="", timezone="")`

`VEVENT`s between two ISO-8601 timestamps. The server expands recurrence. Optional `calendar` collection name or URL.

`start`, `end`, and `timezone` follow [time zones](#time-zones) below. Naive values are wall times. `Z` and numeric offsets are absolute. Returned events include:
- `dtstart`: UTC `YYYY-MM-DDTHH:MM:SSZ`, or `YYYY-MM-DD` when `all_day`
- `dtstart_local`: local time with a numeric offset (e.g. `2026-11-29T16:00:00+01:00`), or the civil date when `all_day`
- `dtend`: UTC timestamp, or the exclusive end date when `all_day`
- `dtend_local`: local timestamp with offset, or the exclusive end date
- `timezone`: IANA name used for the local fields
- `all_day`: boolean
- `calendar`: calendar collection name
- `href` and `etag`: required for update and delete
- `summary`, `location`, `description`, `status`, `uid`

### `calendar_get(href, timezone="")`

Fetch a single event by its href. Returns the rich event object with both UTC and local times.

### `calendar_add(summary, dtstart, dtend, calendar="", location="", description="", timezone="", all_day=False, status="")`

Create. `If-None-Match: *`.

Pass `dtstart` and `dtend` as local wall time (`2026-11-29T16:00:00`). Set `timezone` to an IANA name when it is not already configured. Do not convert that wall time to UTC first. A value with `Z` or a numeric offset is kept as that instant. `all_day=true` or a date (`2026-11-29`) writes `VALUE=DATE`; `dtend` is exclusive, and the same date as `dtstart` means one day. A spring-forward gap or a fall-back overlap without an offset returns `{"error": "..."}`. The stored object uses `TZID` and `VTIMEZONE`, so a server-side weekly rule stays on the same wall clock across DST. Returns the event dictionary.

### `calendar_update(href, etag, summary="", dtstart="", dtend="", location="", description="", timezone="", all_day=None, status="")`

Replace. `If-Match` is the etag from `calendar_list` or `calendar_get`. Empty strings leave that field unchanged. Naive `dtstart` / `dtend` use `timezone` the same way as `calendar_add`. Properties you do not set — including `RRULE`, `EXDATE`, `VALARM`, `ATTENDEE`, and `X-` properties — are copied through. `SEQUENCE` increments. Changing only one bound keeps the other instant when the result is still ordered; if the edit would reverse the span, the previous duration is kept.

### `calendar_delete(href, etag)`

Delete. `If-Match` required.

### Time zones

Resolution order: explicit `timezone`, then `CALDAV_TIMEZONE` or `timezone` in the credentials file, then the collection `calendar-timezone` when it is an IANA id, then the host zone, then `UTC`. Offsets come from the IANA database via `zoneinfo`.
