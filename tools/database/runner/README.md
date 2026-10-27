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

`runner_config` must contain only `backend`, set to `cassandra`, `mariadb`,
`postgresql`, or `redis`. Each session starts one pinned container and removes
it when the session closes. Cassandra, PostgreSQL, and MariaDB apply packaged
schemas that create the objects used by the scenarios but no rows. Redis needs
no initialization beyond its readiness check. Scenarios own any data their
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
| `DATABASE_LOCAL_DATACENTER` | Cassandra local datacenter; absent for other backends |

Cassandra runs without authentication, so `DATABASE_USER` and
`DATABASE_PASSWORD` are empty for that backend.

Connection fields rather than a language-specific URL let Java, Python,
JavaScript, .NET, and future database scenarios construct their native client
configuration from the same backend. SQL packages select their backend's contract
from the shared [`contracts/`](../sql-test-client/contracts) directory using
`scenario_contract`. The generic conformance runner injects only the selected
contract entry's `action` into the scenario process.

Redis scenarios use `DATABASE_NAME` as the logical database index and
authenticate with `DATABASE_USER` and `DATABASE_PASSWORD` only when the password
is non-empty. The Redis backend supplies database zero, user `default`, and an
empty password, so its scenarios run without authentication.

The package classifies only client spans for the backends it can run.
Cassandra, MariaDB, PostgreSQL, and Redis spans use their respective
`db.cassandra.client`, `db.mariadb.client`, `db.postgresql.client`, and
`db.redis.client` refinements. Adding a backend
also requires adding its span classification and conformance scenarios.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
