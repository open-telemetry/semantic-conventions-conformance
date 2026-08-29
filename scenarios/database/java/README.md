# Database conformance scenarios in Java

Java database conformance for PostgreSQL and MariaDB JDBC plus the Couchbase 2.x
and 3.x clients. JDBC is tested through the OpenTelemetry Java agent and the
OpenTelemetry JDBC library instrumentation. Couchbase is tested through the
Java agent.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and initialization stay in the Python runner, where later languages
can reuse them.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/couchbase/couchbase-2/opentelemetry-javaagent
otel-conformance scenarios/database/java/couchbase/couchbase-3/opentelemetry-javaagent
```

Docker must be installed and running.
