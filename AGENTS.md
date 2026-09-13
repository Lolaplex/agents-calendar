# agents-calendar

CalDAV feeler. CLI + MCP. Events only (v0). No CardDAV. No WebDAV files. No RRULE parser — server expands via time-range.

## Commands

```bash
python -m agents_calendar --help-json
python -m agents_calendar calendars
python -m agents_calendar list --from 2026-09-13T00:00:00Z --to 2026-09-14T00:00:00Z
python -m agents_calendar add --summary "Exam" --dtstart 2026-09-14T08:00:00Z --dtend 2026-09-14T10:00:00Z
python -m agents_calendar update --href <href> --etag <etag> --summary "Exam (moved)"
python -m agents_calendar delete --href <href> --etag <etag>
python -m agents_calendar serve
```

Env: `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD` (app password). Never print the password. Never store it in traces, chat, or markdown memory.

Write uses `If-Match` / `If-None-Match`. Missing etag on update/delete is a hard error.

Harness shells this CLI. It does not import this package.
