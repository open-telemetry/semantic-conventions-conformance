# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. PostgreSQL and MariaDB run through JDBC with the
OpenTelemetry Java agent and JDBC library instrumentation. OpenSearch runs
through the Java agent against the REST client before and after its Apache HTTP
client change, plus the current Java client. The database runner starts the
selected Docker container and bootstraps it before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/opensearch/rest-1.0/                   REST client 1.x and 2.x instrumentation
java/opensearch/rest-3.0/                   REST client 3.x instrumentation
java/opensearch/java-3.0/                   Java client 3.x instrumentation
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
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/opensearch/rest-1.0/opentelemetry-javaagent
otel-conformance scenarios/database/java/opensearch/rest-3.0/opentelemetry-javaagent
otel-conformance scenarios/database/java/opensearch/java-3.0/opentelemetry-javaagent
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. Neither seeds data. The
[OpenSearch bootstrap](../../tools/database/runner/src/database_conformance/opensearch-bootstrap.sh)
creates the fixed index and documents used by all three OpenSearch clients.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
