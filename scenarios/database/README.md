# Database conformance scenarios

What database instrumentations emit, checked against the
[database semantic conventions][database] and recorded as committed coverage.

Initial support is Java-only. PostgreSQL and MariaDB run through JDBC against
the OpenTelemetry Java agent and JDBC library instrumentation. Cassandra covers
the driver 3.x, driver 4.0-4.3, and driver 4.4+ agent instrumentation lines. The
current driver 4.4+ package also runs the published Cassandra library
instrumentation. Redis runs through Jedis, Lettuce, Rediscala, and Redisson
against the Java agent, with an additional Lettuce run against its standalone
library instrumentation. The database runner starts the selected Docker
container and applies any required initialization before measured processes start.

```text
java/shared/jdbc/scenarios/                 the JDBC workload, with no OpenTelemetry
java/shared/jdbc/opentelemetry-javaagent/   the shared Java agent launcher
java/shared/jdbc/opentelemetry-library/     the shared library launcher
contracts/                                 Cassandra and Redis telemetry expectations
java/{postgresql,mariadb}/jdbc/             vendor conformance packages
java/shared/cassandra{3,4}/scenarios/        driver-specific workloads
java/shared/cassandra*/opentelemetry-*/      Cassandra launchers
java/cassandra/cassandra-driver-*/           versioned Cassandra packages
java/shared/redis/                          Redis client workloads and launchers
java/redis/{jedis,lettuce,rediscala,redisson}/
                                            Redis conformance packages
../../tools/database/sql-test-client/       combined SQL actions and expectations
```

Each SQL backend's combined contract lives under
[`tools/database/sql-test-client/contracts`](../../tools/database/sql-test-client/contracts).
Each ordered scenario keeps its backend-specific `action` and generic telemetry
`expect` object together. The runner executes each list position under its own
live-check and passes only its selected `action` to the language helper as JSON,
which translates it into its client API. Contracts can diverge as dialect-specific
sanitization and summarization coverage grows.

Each operation is a separate scenario so a missing or malformed span identifies
the client path that produced it:

| Action kind | JDBC path |
| --- | --- |
| `query` | `Statement.executeQuery` |
| `prepared_query` | `PreparedStatement.executeQuery` |
| `batch` | `Statement.executeBatch` |
| `stored_procedure` | `CallableStatement.execute` |

Cassandra keeps its telemetry expectations in
[`contracts/cassandra.yaml`](contracts/cassandra.yaml) and uses one scenario per
native driver path:

| Scenario | Cassandra path |
| --- | --- |
| `query` | Simple CQL query |
| `prepared` | Prepared and bound CQL query |
| `batch` | Two-statement logged batch |
| `error` | Invalid query reported by Cassandra |

Every Redis client runs the same workload with the same keys, values, and
plain-string encoding in logical database zero:

| Scenario | Redis workload |
| --- | --- |
| `set_get` | `SET conformance:value value`, then `GET` and verify the value |
| `pipeline` | Submit `SET conformance:pipeline:1 first` and `SET conformance:pipeline:2 second` before waiting, then `GET` both keys and verify their values |
| `error` | `SET conformance:error not-a-list`, then `LPUSH conformance:error value` and verify `WRONGTYPE` |

Redis contracts live under [`contracts`](contracts) and keep named scenarios
because the Redis launchers select workloads by name rather than consume SQL
`action` objects. Each client's contract records its telemetry for these common
operations, including connection-startup commands. Lettuce's explicit pipelining
and Rediscala's implicit pipelining emit one span per queued command; Jedis and
Redisson expose a pipeline batch span. Rediscala also has a separate
`transaction` scenario that records a `MULTI` batch.

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
otel-conformance scenarios/database/java/redis/jedis/opentelemetry-javaagent
otel-conformance scenarios/database/java/redis/lettuce/opentelemetry-javaagent
otel-conformance scenarios/database/java/redis/lettuce/opentelemetry-library
otel-conformance scenarios/database/java/redis/rediscala/opentelemetry-javaagent
otel-conformance scenarios/database/java/redis/redisson/opentelemetry-javaagent
```

Docker must be installed and running. One database container serves the whole
package run, then is removed. The runner owns the schemas for
[PostgreSQL](../../tools/database/runner/src/database_conformance/postgres.sql),
[MariaDB](../../tools/database/runner/src/database_conformance/mariadb.sql), and
[Cassandra](../../tools/database/runner/src/database_conformance/cassandra.cql).
The Cassandra schema recreates its keyspace and table for each package run.
None of the schemas seed data.

The Redis backend uses logical database zero and requires only a readiness
check. Each scenario uses namespaced keys and verifies its command results.
The pinned container is shared for one package run and removed afterward.

The runs opt into stable database semantic conventions. Java instrumentation
otherwise emits legacy database attributes during the migration period, which
cannot be checked against the stable registry pinned here.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
