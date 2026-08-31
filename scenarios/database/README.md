# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only and exercises PostgreSQL and MariaDB through JDBC.
Each vendor runs against the OpenTelemetry Java agent and the OpenTelemetry JDBC
library instrumentation. The database runner starts the selected Docker
container and applies its shared schema before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
contracts/                                 shared telemetry expectations by vendor
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
```

Contracts contain only telemetry expectations. A language or driver reuses
them by declaring the same scenario names with its own environment and run
commands.

The concrete SQL workload lives in
[`tools/database/sql-test-client/contract.json`](../../tools/database/sql-test-client/contract.json).
It defines each operation, its expected result, and the SQL or procedure name
for every SQL backend. Language helpers read that file and translate named
parameters and procedure calls into their client APIs. Other database families
can define workloads that fit their own data models.

Each operation is a separate scenario so a missing or malformed span identifies
the client path that produced it:

| Scenario | JDBC path |
| --- | --- |
| `statement` | `Statement.executeQuery` |
| `prepared_statement` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
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
