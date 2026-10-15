# Database conformance scenarios in Java

Java JDBC conformance for PostgreSQL and MariaDB, tested through the OpenTelemetry
Java agent and the OpenTelemetry JDBC library instrumentation.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. `shared:jdbc:javaagent-launcher` and
`shared:jdbc:library-launcher` hold the entry points that configure either the
Java agent or `opentelemetry-jdbc`. Vendor directories contain the conformance
configuration, coverage, and the launch project a target prepares, which adds
only that vendor's driver. Each target's `artifacts.json` therefore records the
driver it actually ran against. Another PostgreSQL client such as Vert.x SQL can
sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
