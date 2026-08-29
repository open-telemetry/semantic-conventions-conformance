# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. It exercises PostgreSQL and MariaDB through JDBC,
and Couchbase through the 2.x and 3.x Java client APIs. JDBC runs against the
OpenTelemetry Java agent and the OpenTelemetry JDBC library instrumentation.
Couchbase runs against the Java agent. The database runner starts and initializes
the selected Docker container before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/couchbase-{2,3}/                 API-line-specific Java agent launchers
java/couchbase/couchbase-{2,3}/              Couchbase conformance packages
```

Each operation is a separate scenario so a missing or malformed span identifies
the JDBC path that produced it:

| Scenario | JDBC path |
| --- | --- |
| `statement` | `Statement.executeQuery` |
| `prepared_statement` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

Couchbase exercises successful upsert and get calls plus a missing-document
error on both supported client API lines. The 3.x scenarios use the named
`conformance.items` collection. The 2.x client predates collections and uses the
bucket's default collection.

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/couchbase/couchbase-2/opentelemetry-javaagent
otel-conformance scenarios/database/java/couchbase/couchbase-3/opentelemetry-javaagent
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. Neither seeds data. The runner initializes the digest-pinned Couchbase
Community Server 7.6.2 image through its command-line tools with one bucket,
scope, and collection.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

The pinned registry has no Couchbase-specific client span refinement, so
Couchbase spans contribute to the general `db.client` coverage type.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
