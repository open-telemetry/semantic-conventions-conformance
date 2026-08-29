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

Each conformance package has a `database.yaml` that selects its backend:

```yaml
backend: postgresql
```

The supported values are `postgresql` and `mariadb`. Each session starts one
pinned container, applies that backend's packaged SQL schema, and removes the
container when the session closes. The schemas create the same logical objects
but no rows; scenarios own any data their operations need.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable | Value |
| --- | --- |
| `DATABASE_HOST` | Loopback address published by Docker |
| `DATABASE_PORT` | Docker-assigned host port |
| `DATABASE_NAME` | Test database name |
| `DATABASE_USER` | Test user |
| `DATABASE_PASSWORD` | Test-only password |

Connection fields rather than a language-specific URL let Java, Python,
JavaScript, .NET, and future database scenarios construct their native client
configuration from the same backend.

The package gives each database client span one semantic-convention identity.
PostgreSQL and MariaDB spans use `db.postgresql.client` and
`db.mariadb.client`. Other SQL systems use `db.sql.client`, and non-SQL database
clients use `db.client`.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
