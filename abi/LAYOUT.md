# Credentials

No event store on disk. The only host file is the password file.

Resolution order, first hit wins:

1. Process environment `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`, optional `CALDAV_CALENDAR` (default collection for `add`, by display name or URL), and optional `CALDAV_TIMEZONE` (IANA name).
2. `AGENTS_HOME/calendar.json` or `~/.agents/calendar.json`. Keys: `url`, `username`, `password`, optional `calendar`, optional `timezone`. Create it mode `0600`. Do not commit it.
3. `AGENTS_HOME/.env` or `~/.agents/.env`, same names as the environment variables.

`timezone` does not select the zone by itself when a call passes `timezone` or `--timezone`. The full order is that argument, then `CALDAV_TIMEZONE` / the file, then the collection's CalDAV `calendar-timezone`, then the host zone, then `UTC`.

`sync --init` and `init` merge the MCP command into host configs. They do not write the password into those files. A desktop MCP host inherits nothing from a random shell, so the JSON file is how that host sees the calendar.

A URL that is only a host or a principal is not the PUT target. The client discovers the calendar home, then a `VEVENT` collection.
