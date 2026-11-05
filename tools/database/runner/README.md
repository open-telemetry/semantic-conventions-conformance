# Database conformance

Runs a conformance directory against the
[database semantic conventions][database], with the upstream registry and
coverage reduction already wired in.

```sh
pip install -e tools/runner -e tools/database/runner
database-conformance path/to/directory
```

A directory declaring `runner: database-conformance` gets the same wiring from
plain `otel-conformance` and from `pytest`. See the
[conformance directory format](../../runner/README.md). Docker and a running
daemon are required.

Each package selects a registered backend selector in `conformance.yaml`:

```yaml
runner: database-conformance
runner_config:
  backend: postgresql
```

`runner_config` must contain exactly one string key, `backend`. The authoritative
selector-to-factory and semantic-convention registration is in
[`_registry.py`](src/database_conformance/_registry.py). A session starts one
container, waits for its declared readiness check, applies any declared
initialization, and removes the container when the session closes. Workloads
normally create or verify their own data. The HBase fixture seeds its read row
and uses fixed ports; its initialization, image pinning, and concurrency limits
are documented in the [HBase scenario notes](../../../scenarios/database/java/hbase/README.md).
MongoDB uses deterministic bootstrap fixtures as
described in its [backend notes](../../../scenarios/database/java/mongodb/README.md).

Backend readiness timeouts default to 60 seconds, 120 seconds for MySQL, and
180 seconds for Cassandra and Oracle. Set
`OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT` in the runner's environment to
override any backend's default:

```sh
OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT=240 database-conformance path/to/directory
```

The shared container lifecycle reads this value, not `conformance.yaml` or the
workload environment. It must be a finite positive number of seconds; invalid
values produce a warning and use the backend's default.

See the [Oracle scenario notes](../../../scenarios/database/java/oracle/README.md)
for its container initialization, and the
[MySQL scenario notes](../../../scenarios/database/java/mysql/README.md) for its
container setup.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable            | Value                                        |
| ------------------- | -------------------------------------------- |
| `DATABASE_HOST`     | Loopback address published by Docker         |
| `DATABASE_PORT`     | Published host port; fixed for HBase         |
| `DATABASE_NAME`     | Test database name or logical database index |
| `DATABASE_USER`     | Test user                                    |
| `DATABASE_PASSWORD` | Test-only password                           |

Connection fields let each language construct its native client configuration.
Packages using indexed SQL contracts select a contract under
[`contracts/`](../sql-test-client/contracts) using `scenario_contract`. The
generic conformance runner injects only the selected contract entry's `action`
into the scenario process. Named telemetry-only contracts, such as
[R2DBC's](../../../scenarios/database/java/shared/r2dbc/README.md), instead
declare a run command for each scenario.
Backend-specific initialization and connection details for Elasticsearch are in
its [scenario notes](../../../scenarios/database/java/elasticsearch/README.md).

Cassandra's additional connection variable and container prerequisites are
documented in its [scenario notes](../../../scenarios/database/java/cassandra/README.md).

The classifier recognizes registered semantic-convention systems only on
`CLIENT` spans and only when their client span type exists in the resolved
coverage registry. The system identifiers and span types are defined alongside
backend construction in [`_registry.py`](src/database_conformance/_registry.py).

[database]: https://opentelemetry.io/docs/specs/semconv/db/
