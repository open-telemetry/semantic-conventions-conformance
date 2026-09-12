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

`runner_config` must contain only `backend`, set to `hbase-1`, `hbase-2`,
`mariadb`, or `postgresql`. Each session starts one pinned container fixture,
applies that backend's packaged schema, and removes the container when the
session closes. PostgreSQL and MariaDB create the same empty logical objects.
HBase creates its table and one deterministic row for read scenarios.

The HBase fixtures build local images from checksum-verified Apache HBase
1.7.2 and 2.4.18 binary distributions and a digest-pinned Eclipse Temurin
base, then remove each image when its session closes. Each client runs
against its matching server API line. HBase advertises fixed ZooKeeper,
master, and region-server ports, so only one HBase conformance session can
run on a host at a time. Startup failures include the fixture's container
logs.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable | Value |
| --- | --- |
| `DATABASE_HOST` | Loopback address published by Docker |
| `DATABASE_PORT` | Published host port; Docker-assigned for PostgreSQL and MariaDB, 2181 for HBase |
| `DATABASE_NAME` | Test database name |
| `DATABASE_USER` | Test user |
| `DATABASE_PASSWORD` | Test-only password |

Connection fields rather than a language-specific URL let Java, Python,
JavaScript, .NET, and future database scenarios construct their native client
configuration from the same backend.

The package classifies only spans for the backends it can run. PostgreSQL spans
use `db.postgresql.client`, MariaDB spans use `db.mariadb.client`, and HBase
spans use `db.hbase.client`. Adding a backend also requires adding its span
classification and conformance scenarios.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
