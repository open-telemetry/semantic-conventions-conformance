# Database conformance scenarios in Java

Java database conformance for PostgreSQL and MariaDB JDBC, plus PostgreSQL
R2DBC. Each client is tested through the OpenTelemetry Java agent and the
matching OpenTelemetry library instrumentation.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The `shared:r2dbc:scenarios` project likewise owns one reactive workload. Its
launchers create the same PostgreSQL `ConnectionFactory`, then either let the
Java agent instrument it or wrap it with `opentelemetry-r2dbc-1.0`.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-library
```

Docker must be installed and running.
