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
contracts/                                 shared telemetry expectations by vendor
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/mongodb/{sync,async,reactive}/  MongoDB workloads and launchers
java/mongodb/{sync,async,reactive}/         MongoDB conformance packages
```

Contracts contain only telemetry expectations. A language or driver reuses
them by declaring the same scenario names with its own environment and run
commands.

Each operation is a separate scenario so a missing or malformed span identifies
the JDBC path that produced it:

| Scenario | JDBC path |
| --- | --- |
| `statement` | `Statement.executeQuery` |
| `prepared_statement` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

MongoDB packages use the same operation set across all three driver APIs:

| Scenario | MongoDB command |
| --- | --- |
| `find` | `find` by `_id` |
| `update` | `updateOne` by `_id` |
| `delete` | `deleteOne` by `_id` |
| `aggregate` | one-stage `$match` aggregation |

Each expectation also accounts for the driver's `endSessions` command when the
client closes.

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
