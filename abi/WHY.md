# Why agents-calendar exists

Version: see [`VERSION`](VERSION).

Agents need to read and write one calendar. They do not need a CalDAV framework, an iCalendar recurrence engine, or a password inside `mcp.json`.

This package speaks HTTP from the standard library. Recurrence expansion is a CalDAV time-range query, so the server applies `RRULE`. Creates send `If-None-Match: *`. Updates and deletes send `If-Match` with the etag from `calendar_list`. A stale etag fails instead of overwriting.

`add` writes into a collection that accepts `VEVENT`. A calendar-home or principal URL is resolved through `calendar-home-set`. Reminder collections that only allow `VTODO` are skipped.
