# Database conformance

Runs a conformance directory against the
[database semantic conventions][database], with the upstream registry and
coverage reduction already wired in.

```sh
pip install -e tools/runner -e tools/database/runner
database-conformance path/to/directory
```

A directory declaring `runner: database-conformance` gets the same wiring from
plain `otel-conformance` and from `pytest`. See
[`tools/runner/README.md`](../../runner/README.md) for the conformance directory
format. Docker must be installed and its daemon running.

Each session starts one pinned PostgreSQL container, applies
[`postgres.sql`](src/database_conformance/postgres.sql), and removes the
container when the session closes. The schema creates shared objects but no
rows; scenarios own any data their operations need.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable | Value |
| --- | --- |
| `POSTGRES_HOST` | Loopback address published by Docker |
| `POSTGRES_PORT` | Docker-assigned host port |
| `POSTGRES_DATABASE` | Test database name |
| `POSTGRES_USER` | Test role |
| `POSTGRES_PASSWORD` | Test-only password |

Connection fields rather than a language-specific URL let Java, Python,
JavaScript, .NET, and future database scenarios construct their native client
configuration from the same backend.

The package classifies every client span carrying `db.system.name` as the
general `db.client` type. SQL database systems are also classified as
`db.sql.client`, so their SQL-specific attributes are recorded without losing
coverage of the general database conventions.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
