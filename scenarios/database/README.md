# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only and exercises JDBC through the OpenTelemetry Java
agent. The database runner starts an ephemeral PostgreSQL Docker container and
applies the shared schema before any measured process starts.

```text
java/jdbc/scenarios/                  the JDBC workload, with no OpenTelemetry
java/jdbc/opentelemetry-javaagent/    the launcher and conformance package
```

Each operation is a separate scenario so a missing or malformed span identifies
the JDBC path that produced it:

| Scenario | JDBC path |
| --- | --- |
| `statement` | `Statement.executeQuery` |
| `prepared_statement` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/jdbc/opentelemetry-javaagent
```

Docker must be installed and running. One PostgreSQL container serves the whole
package run, then is removed. Its
[`postgres.sql`](../../tools/database/runner/src/database_conformance/postgres.sql)
schema contains empty tables and the stored procedure the workloads call; it
does not seed data.

The run opts into the Java agent's stable database semantic conventions. The
agent otherwise emits the legacy database attributes during its migration
period, which cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
