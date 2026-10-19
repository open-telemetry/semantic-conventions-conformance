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
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/r2dbc/scenarios/                the reactive R2DBC workload
java/shared/r2dbc/opentelemetry-javaagent/  the R2DBC Java agent launcher
java/shared/r2dbc/opentelemetry-library/    the R2DBC library launcher
java/postgresql/r2dbc/                      the PostgreSQL R2DBC packages
../../tools/database/sql-test-client/       combined SQL actions and expectations
contracts/postgresql-r2dbc.yaml             R2DBC telemetry expectations
```

The JDBC packages use each backend's combined SQL contract under
[`tools/database/sql-test-client/contracts`](../../tools/database/sql-test-client/contracts).
Each ordered scenario keeps its backend-specific `action` and generic telemetry
`expect` object together. The runner executes each list position under its own
live-check and passes only its selected `action` to the language helper as JSON,
which translates it into its client API. Contracts can diverge as dialect-specific
sanitization and summarization coverage grows.

The R2DBC packages use the named scenarios in
[`contracts/postgresql-r2dbc.yaml`](contracts/postgresql-r2dbc.yaml). This contract
contains only telemetry expectations; the reactive workload owns the SQL. It
stays separate because R2DBC emits different namespace and bind-marker attributes
and also covers a handled SQL error. Both instrumentation modes share this
contract and workload.

Each operation is a separate scenario so a missing or malformed span identifies
the client path that produced it:

| Action kind | JDBC path |
| --- | --- |
| `query` | `Statement.executeQuery` |
| `prepared_query` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

The R2DBC packages exercise a plain `Statement`, a bound `Statement`, a
two-command `Batch`, a stored procedure through `Statement`, and an invalid
query that produces PostgreSQL SQLSTATE `42P01`. Every publisher is consumed
before the connection closes.

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
