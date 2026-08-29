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

The supported values are `postgresql`, `mariadb`, and `opensearch`. Each
session starts one digest-pinned container, applies its packaged bootstrap
resource, and removes the container when the session closes. The SQL schemas
create the same empty logical objects. The OpenSearch bootstrap creates a
single-shard `conformance` index with two fixed documents.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable | Value |
| --- | --- |
| `DATABASE_HOST` | Loopback address published by Docker |
| `DATABASE_PORT` | Docker-assigned host port |
| `DATABASE_NAME` | Test database or index name |
| `DATABASE_USER` | Test user, empty when the backend has no authentication |
| `DATABASE_PASSWORD` | Test-only password, empty when authentication is disabled |

Connection fields rather than a language-specific URL let Java, Python,
JavaScript, .NET, and future database scenarios construct their native client
configuration from the same backend.

The package gives each database client span one semantic-convention identity.
PostgreSQL and MariaDB spans use `db.postgresql.client` and
`db.mariadb.client`. Other SQL systems use `db.sql.client`. OpenSearch and
other non-SQL systems use `db.client` because the pinned registry has no
OpenSearch-specific span refinement.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
