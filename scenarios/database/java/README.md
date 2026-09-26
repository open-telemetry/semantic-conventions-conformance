# Database conformance scenarios in Java

Java conformance for PostgreSQL, MariaDB, and HBase. JDBC is tested through
the OpenTelemetry Java agent and the OpenTelemetry JDBC library
instrumentation. HBase 1.x and 2.x client APIs are tested through the Java
agent.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

The HBase scenarios use the latest client in each API range covered by the
agent's dedicated instrumentation: 1.7.x and 2.4.x.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
