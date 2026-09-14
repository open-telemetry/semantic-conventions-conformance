# Database conformance scenarios in Java

Java database conformance for PostgreSQL and MariaDB through JDBC, plus MongoDB
synchronous, legacy asynchronous, and Reactive Streams drivers. Every client is
tested through the OpenTelemetry Java agent and the corresponding published
standalone instrumentation library.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and bootstrap stay in the Python runner, where later languages can
reuse them.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/sync/opentelemetry-javaagent
```

Docker must be installed and running.
