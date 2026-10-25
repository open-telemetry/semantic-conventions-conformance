# Database conformance scenarios in Java

Java database conformance for PostgreSQL, MariaDB, HBase, and Redis. JDBC is
tested through the OpenTelemetry Java agent and JDBC library instrumentation.
HBase 1.x and 2.x client APIs are tested through the Java agent. Jedis, Lettuce,
Rediscala, and Redisson are also tested through the Java agent, and Lettuce
additionally exercises its supported standalone library instrumentation.

The language-neutral SQL actions and telemetry expectations live together in
backend-specific files under
[`tools/database/sql-test-client/contracts`](../../../tools/database/sql-test-client/contracts).
The runner injects the selected action as JSON. The `shared:jdbc:scenarios`
Gradle project parses it through `SqlContract` and translates it into JDBC. Its
launcher projects configure either the Java agent or `opentelemetry-jdbc`.
Vendor directories contain the conformance configuration and coverage, so
another PostgreSQL client such as Vert.x SQL can sit beside JDBC without
duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

The HBase scenarios use the latest client in each API range covered by the
agent's dedicated instrumentation: 1.7.x and 2.4.x.
Use Java 25 for the Gradle build and keep `JAVA_HOME` on that JDK, matching CI.
The HBase workload, launchers, and their shared scenario-support and agent-control
projects select Java 21 toolchains; Gradle provisions that JDK when needed.
The prepared HBase runtimes record Java 21, while JDBC and Redis retain the
Java 25 default. The HBase clients' Hadoop dependencies call `Subject.getSubject`,
which is no longer supported on Java 24 and later, so changing only the build
JDK would not make those dependencies compatible at runtime.

For both HBase client lines, the Java agent reports the ZooKeeper cluster key
(`127.0.0.1:2181:/hbase`) as `server.address`, with no separate `server.port`.
The shared contract checks that cluster address rather than the region-server
RPC endpoint. The committed coverage records the attributes CI observed.

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
