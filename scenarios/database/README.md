# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. PostgreSQL and MariaDB run through JDBC, each
against the OpenTelemetry Java agent and the OpenTelemetry JDBC library
instrumentation. HBase runs through the 1.x and 2.x client APIs, against the
Java agent. The database runner starts the selected Docker container and
applies its shared schema before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
java/shared/hbase/scenarios/                the HBase workload, with no OpenTelemetry
contracts/                                 shared telemetry expectations by vendor
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/hbase/{hbase-1,hbase-2}/               vendor conformance packages
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

The HBase packages split their operations the same way:

| Scenario | HBase client call |
| --- | --- |
| `get` | `Table.get` |
| `put` | `Table.put` |
| `scan` | `Table.getScanner` |
| `batch` | `Table.batch` |

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/hbase/hbase-1/opentelemetry-javaagent
otel-conformance scenarios/database/java/hbase/hbase-2/opentelemetry-javaagent
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. Neither seeds data. The
[HBase](../../tools/database/runner/src/database_conformance/hbase.rb) schema
creates the namespace and table its workload uses and seeds the one row the
read scenarios expect.

The HBase fixtures publish fixed loopback ports, so only one HBase package can
run at a time on a host.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
