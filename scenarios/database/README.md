# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. It exercises PostgreSQL and MariaDB through JDBC,
plus PostgreSQL through R2DBC. Each client runs against the OpenTelemetry Java
agent and its OpenTelemetry library instrumentation. The database runner starts
the selected Docker container and applies its shared schema before any measured
process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
contracts/                                 shared telemetry expectations by vendor
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/r2dbc/scenarios/                the reactive R2DBC workload
java/shared/r2dbc/opentelemetry-javaagent/  the R2DBC Java agent launcher
java/shared/r2dbc/opentelemetry-library/    the R2DBC library launcher
java/postgresql/r2dbc/                      the PostgreSQL R2DBC packages
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

The R2DBC packages exercise a plain `Statement`, a bound `Statement`, a
two-command `Batch`, and an invalid query that produces PostgreSQL SQLSTATE
`42P01`. Every publisher is consumed before the connection closes.

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-library
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. Neither seeds data.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
