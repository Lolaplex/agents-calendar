# Credentials

No event store on disk. The only host file is the password file.

Resolution order, first hit wins:

1. Process environment `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`, and optional `CALDAV_CALENDAR` (default collection for `add`, by display name or URL).
2. `AGENTS_HOME/calendar.json` or `~/.agents/calendar.json`. Keys: `url`, `username`, `password`, optional `calendar`. Create it mode `0600`. Do not commit it.
3. `AGENTS_HOME/.env` or `~/.agents/.env`, same names as the environment variables.

`sync --init` and `init` merge the MCP command into host configs. They do not write the password into those files. A desktop MCP host inherits nothing from a random shell, so the JSON file is how that host sees the calendar.

A URL that is only a host or a principal is not the PUT target. The client discovers the calendar home, then a `VEVENT` collection.
