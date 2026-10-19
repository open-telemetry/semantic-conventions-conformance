# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. PostgreSQL and MariaDB run through JDBC, while
MongoDB covers the synchronous, legacy asynchronous, and Reactive Streams
drivers. Each client runs against the OpenTelemetry Java agent and its published
standalone instrumentation library. The database runner starts the selected
Docker container and applies its shared bootstrap before any measured process
starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
../../tools/database/sql-test-client/       combined SQL actions and expectations
java/shared/mongodb/{sync,async,reactive}/  MongoDB workloads and launchers
java/mongodb/{sync,async,reactive}/         MongoDB conformance packages
contracts/mongodb.yaml                     shared MongoDB telemetry expectations
```

The PostgreSQL and MariaDB combined SQL contracts live under
[`tools/database/sql-test-client/contracts`](../../tools/database/sql-test-client/contracts).
Each ordered scenario keeps its backend-specific `action` and generic telemetry
`expect` object together. The runner executes each list position under its own
live-check and passes only its selected `action` to the language helper as JSON,
which translates it into its client API. Contracts can diverge as dialect-specific
sanitization and summarization coverage grows.

Each operation is a separate scenario so a missing or malformed span identifies
the client path that produced it:

| Action kind | JDBC path |
| --- | --- |
| `query` | `Statement.executeQuery` |
| `prepared_query` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

MongoDB packages share named telemetry expectations in
[`contracts/mongodb.yaml`](contracts/mongodb.yaml), with driver-specific run
commands. They use the same operation set across all three driver APIs:

| Scenario | MongoDB command |
| --- | --- |
| `find` | `find` by `_id` |
| `update` | `updateOne` by `_id` |
| `delete` | `deleteOne` by `_id` |
| `aggregate` | one-stage `$match` aggregation |

Each expectation also accounts for the driver's `endSessions` command when the
client closes. The standalone library launchers pass the driver's configured
seed addresses to `MongoTelemetry.createCommandListener` so stable
`server.address` and `server.port` describe the same target as the agent runs.

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mongodb/sync/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/sync/opentelemetry-library
otel-conformance scenarios/database/java/mongodb/async/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/async/opentelemetry-library
otel-conformance scenarios/database/java/mongodb/reactive/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/reactive/opentelemetry-library
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. The
[MongoDB bootstrap](../../tools/database/runner/src/database_conformance/mongodb.js)
recreates its collection and seed documents before each package run.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
