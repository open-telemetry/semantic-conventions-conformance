# Database conformance scenarios in Java

Java database conformance for PostgreSQL, MariaDB, and OpenSearch. JDBC runs
through the OpenTelemetry Java agent and JDBC library instrumentation.
OpenSearch runs through the Java agent.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

OpenSearch has one project for each Java agent instrumentation range. REST
client 2.19.6 covers the `[1.0,3.0)` line, REST client 3.8.0 covers `[3.0,)`,
and Java client 3.9.0 covers its `[3.0,)` line. Each client runs cluster health,
document lookup, and search operations against the same bootstrapped index.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
