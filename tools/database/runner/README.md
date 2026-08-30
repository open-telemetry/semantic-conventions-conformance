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

Each conformance package selects its backend in `conformance.yaml`:

```yaml
runner: database-conformance
runner_config:
  backend: postgresql
```

`runner_config` must contain only `backend`, set to `cassandra`, `mariadb`, or
`postgresql`. Each session starts one pinned container, applies that backend's
packaged schema, and removes the container when the session closes. The schemas
create the objects used by the scenarios but no rows; scenarios own any data
their operations need.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable | Value |
| --- | --- |
| `DATABASE_HOST` | Loopback address published by Docker |
| `DATABASE_PORT` | Docker-assigned host port |
| `DATABASE_NAME` | Test database name |
| `DATABASE_USER` | Test user |
| `DATABASE_PASSWORD` | Test-only password |
| `DATABASE_LOCAL_DATACENTER` | Cassandra local datacenter; absent for SQL backends |

Connection fields rather than a language-specific URL let Java, Python,
JavaScript, .NET, and future database scenarios construct their native client
configuration from the same backend.

The package classifies only spans for the backends it can run. Cassandra,
MariaDB, and PostgreSQL spans use their respective `db.cassandra.client`,
`db.mariadb.client`, and `db.postgresql.client` refinements. Adding a backend
also requires adding its span classification and conformance scenarios.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
