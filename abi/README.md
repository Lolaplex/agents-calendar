# agents-calendar ABI

Version: see [`VERSION`](VERSION).

CalDAV feeler. Stdlib HTTP. The Python package in this repository is the reference implementation. MCP tools mirror the CLI. The password is never part of a tool or CLI payload.

| Doc | Contract |
| --- | --- |
| [`WHY.md`](WHY.md) | Server-side recurrence, etags, host credentials |
| [`LAYOUT.md`](LAYOUT.md) | Where the password lives |
| [`MCP.md`](MCP.md) | Five tools |
| [`CLI.md`](CLI.md) | The same verbs, plus `init` |

Machine-readable command list: `python -m agents_calendar --help-json`.
