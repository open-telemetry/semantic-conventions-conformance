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

`runner_config` must contain only `backend`, set to `postgresql`, `mariadb`, or
`redis`. Each session starts one pinned container, initializes it, and removes
it when the session closes. PostgreSQL and MariaDB apply packaged SQL schemas
that create the same logical objects but no rows. Redis runs `redis-cli` to
create the `conformance:bootstrap` key. Scenarios own any other data their
operations need.

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

The package classifies only client spans for the backends it can run.
PostgreSQL spans use `db.postgresql.client`, MariaDB spans use
`db.mariadb.client`, and Redis spans use `db.redis.client`. Adding a backend
also requires adding its span classification and conformance scenarios.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
