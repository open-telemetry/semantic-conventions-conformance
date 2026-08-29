# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. PostgreSQL and MariaDB run through JDBC against
the OpenTelemetry Java agent and JDBC library instrumentation. Cassandra covers
the driver 3.x, driver 4.0-4.3, and driver 4.4+ agent instrumentation lines. The
current driver 4.4+ package also runs the published Cassandra library
instrumentation. The database runner starts the selected Docker container and
applies its shared schema before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
contracts/                                 shared telemetry expectations by vendor
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/cassandra{3,4}/scenarios/        driver-specific workloads
java/shared/cassandra*/opentelemetry-*/      Cassandra launchers
java/cassandra/cassandra-driver-*/           versioned Cassandra packages
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

Cassandra uses one scenario per native driver path:

| Scenario | Cassandra path |
| --- | --- |
| `query` | Simple CQL query |
| `prepared` | Prepared and bound CQL query |
| `batch` | Two-statement logged batch |
| `error` | Invalid query reported by Cassandra |

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/cassandra/cassandra-driver-3/opentelemetry-javaagent
otel-conformance scenarios/database/java/cassandra/cassandra-driver-4.3/opentelemetry-javaagent
otel-conformance scenarios/database/java/cassandra/cassandra-driver-4.19/opentelemetry-javaagent
otel-conformance scenarios/database/java/cassandra/cassandra-driver-4.19/opentelemetry-library
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql), and
[Cassandra](../../tools/database/runner/src/database_conformance/cassandra.cql)
schemas. The Cassandra schema recreates its keyspace and table for each package
run. None of the schemas seed data.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
