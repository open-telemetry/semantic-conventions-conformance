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
initialization, and removes the container when the session closes. Scenario data
is not pre-seeded; each workload creates or verifies the data it needs.

Conformance packages can use these runner variables in setup and scenario
environment declarations:

| Variable            | Value                                        |
| ------------------- | -------------------------------------------- |
| `DATABASE_HOST`     | Loopback address published by Docker         |
| `DATABASE_PORT`     | Docker-assigned host port                    |
| `DATABASE_NAME`     | Test database name or logical database index |
| `DATABASE_USER`     | Test user                                    |
| `DATABASE_PASSWORD` | Test-only password                           |
| `DATABASE_LOCAL_DATACENTER` | Cassandra local datacenter |

Cassandra runs without authentication, so `DATABASE_USER` and
`DATABASE_PASSWORD` are empty for that backend.

Connection fields let each language construct its native client configuration.
SQL packages select a contract under
[`contracts/`](../sql-test-client/contracts) using `scenario_contract`. The
generic conformance runner injects only the selected contract entry's `action`
into the scenario process.

The classifier recognizes registered semantic-convention systems only on
`CLIENT` spans and only when their client span type exists in the resolved
coverage registry. The system identifiers and span types are defined alongside
backend construction in [`_registry.py`](src/database_conformance/_registry.py).

[database]: https://opentelemetry.io/docs/specs/semconv/db/
