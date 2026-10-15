# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. It exercises PostgreSQL and MariaDB through JDBC,
and Redis through Jedis, Lettuce, Rediscala, and Redisson. JDBC runs against the
OpenTelemetry Java agent and JDBC library instrumentation. Redis runs against
the Java agent, with an additional Lettuce run against its standalone library
instrumentation. The database runner starts the selected Docker container and
initializes it before any measured process starts.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
contracts/                                 shared telemetry expectations by backend/client
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/redis/                          Redis client workloads and launchers
java/redis/{jedis,lettuce,rediscala,redisson}/
                                            Redis conformance packages
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

Every Redis client runs the same workload with the same keys, values, and
plain-string encoding in logical database zero:

| Scenario | Redis workload |
| --- | --- |
| `set_get` | `SET conformance:value value`, then `GET` and verify the value |
| `pipeline` | Submit `SET conformance:pipeline:1 first` and `SET conformance:pipeline:2 second` before waiting, then `GET` both keys and verify their values |
| `error` | `SET conformance:error not-a-list`, then `LPUSH conformance:error value` and verify `WRONGTYPE` |

Contracts record client-specific telemetry for these common operations,
including connection-startup commands. Lettuce's explicit pipelining and
Rediscala's implicit pipelining emit one span per queued command; Jedis and
Redisson expose a pipeline batch span. Rediscala also has a separate
`transaction` scenario that records a `MULTI` batch.

## Running it

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mariadb/jdbc/opentelemetry-library
otel-conformance scenarios/database/java/redis/jedis/opentelemetry-javaagent
otel-conformance scenarios/database/java/redis/lettuce/opentelemetry-javaagent
otel-conformance scenarios/database/java/redis/lettuce/opentelemetry-library
otel-conformance scenarios/database/java/redis/rediscala/opentelemetry-javaagent
otel-conformance scenarios/database/java/redis/redisson/opentelemetry-javaagent
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql)
and
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql)
schemas. Both contain the empty table and stored procedure used by the shared
workload. Neither seeds data.

The Redis backend selects logical database zero and writes one bootstrap key.
Each scenario uses namespaced keys and verifies its command results. The pinned
container is shared for one package run and removed afterward.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
