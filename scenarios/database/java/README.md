# Database conformance scenarios in Java

Java database conformance for PostgreSQL, MariaDB, and Redis. JDBC is tested
through the OpenTelemetry Java agent and JDBC library instrumentation. Jedis,
Lettuce, Rediscala, and Redisson are tested through the Java agent, and Lettuce
also exercises its supported standalone library instrumentation.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

Redis client workloads live under `shared:redis`. They cover reads and writes,
batching or transactions where the client exposes them, and a `WRONGTYPE`
server error. Expectations intentionally record client differences: Rediscala
does not emit query text, while Jedis does not currently mark the rejected
command as an error.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
