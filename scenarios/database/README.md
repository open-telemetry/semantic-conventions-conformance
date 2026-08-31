# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. PostgreSQL and MariaDB exercise JDBC through the
OpenTelemetry Java agent and the OpenTelemetry JDBC library instrumentation.
Elasticsearch exercises the REST, Java API, and Transport clients through the
Java agent. The database runner starts the selected Docker container and
applies that backend's packaged schema before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
contracts/                                 shared telemetry expectations by vendor or client API
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/elasticsearch/                  one Java agent launcher per client API
java/elasticsearch/                         Elasticsearch conformance packages
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

The Elasticsearch scenarios cover one current version from each distinct
instrumented client API:

| Scenario package | Client | Version | Operation |
| --- | --- | --- | --- |
| `elasticsearch/rest` | Low Level REST Client | 7.17.29 | `_count` |
| `elasticsearch/api-client` | Elasticsearch Java API Client | 7.17.19 | `search` |
| `elasticsearch/transport` | Transport Client | 7.17.29 | `prepareSearch` |

The Java API Client stays at 7.17.19 because 7.17.20 and later have native
OpenTelemetry instrumentation. This suite measures the Java agent
instrumentation line instead.

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/elasticsearch/rest/opentelemetry-javaagent
otel-conformance scenarios/database/java/elasticsearch/api-client/opentelemetry-javaagent
otel-conformance scenarios/database/java/elasticsearch/transport/opentelemetry-javaagent
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. Neither seeds data. The runner creates Elasticsearch's `conformance`
index from a fixed mapping with one shard, no replicas, and refreshes disabled.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
