# Database conformance scenarios in Java

Java database conformance for PostgreSQL and MariaDB JDBC, PostgreSQL R2DBC,
and Redis. JDBC and R2DBC are tested through the OpenTelemetry Java agent and
their matching library instrumentation. Jedis, Lettuce, Rediscala, and Redisson
are tested through the Java agent, and Lettuce also exercises its supported
standalone library instrumentation.

For JDBC, language-neutral SQL actions and telemetry expectations live together in
backend-specific files under
[`tools/database/sql-test-client/contracts`](../../../tools/database/sql-test-client/contracts).
The runner injects the selected action as JSON. The `shared:jdbc:scenarios`
Gradle project parses it through `SqlContract` and translates it into JDBC. Its
launcher projects configure either the Java agent or `opentelemetry-jdbc`.
Vendor directories contain the conformance configuration and coverage, so
another PostgreSQL client such as Vert.x SQL can sit beside JDBC without
duplicating the shared JDBC code.

The `shared:r2dbc:scenarios` project likewise owns one reactive workload. Its
launchers create the same PostgreSQL `ConnectionFactory`, then either let the
Java agent instrument it or wrap it with `opentelemetry-r2dbc-1.0`. Unlike JDBC,
this workload owns its SQL and selects operations by name. Its telemetry
expectations live in
[`contracts/postgresql-r2dbc.yaml`](../contracts/postgresql-r2dbc.yaml), accounting
for R2DBC-specific namespace and bind-marker attributes. The workload covers
statements, parameter binding, batches, stored procedures, and handled SQL errors.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

Redis client workloads live under `shared:redis`. Every client runs the same
`set_get`, `pipeline`, and `error` operations described in the
[Redis workload](../README.md), with identical keys, values, and plain-string
encoding. Rediscala additionally exercises a transaction.

All Redis launchers use the runner's host, port, database index, user, and
password. An empty password disables authentication. The shared backend
provides database zero without authentication.

Jedis disables protocol negotiation and `CLIENT SETINFO` so its workload
telemetry excludes connection-startup commands.

Expectations intentionally record client differences: Rediscala
does not emit query text, while Jedis does not currently mark the rejected
command as an error. Lettuce records the Redis server's `WRONGTYPE` code in
`error.type` rather than the Java exception class.

All five Redis packages omit `db.response.status_code` on rejected `LPUSH`
spans. The contracts do not assert it while
[#384](https://github.com/open-telemetry/semantic-conventions-conformance/issues/384)
tracks recording conditional semantic-convention violations as findings.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-library
```

Docker must be installed and running.

Redis connection tests use Docker and prepared scenario runtimes to check
database selection and authentication:

```sh
python -m pytest tools/database/runner/tests/test_redis_clients.py
```

Clients whose runtimes have not been prepared are skipped. Linux CI prepares all
five runtimes and requires all 15 database-selection and authentication cases to
run without skips.
