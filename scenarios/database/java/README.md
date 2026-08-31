# Database conformance scenarios in Java

Java JDBC conformance for PostgreSQL and MariaDB, tested through the OpenTelemetry
Java agent and the OpenTelemetry JDBC library instrumentation.

The language-neutral SQL actions and telemetry expectations live together in
backend-specific files under
[`tools/database/sql-test-client/contracts`](../../../tools/database/sql-test-client/contracts).
The `shared:jdbc:scenarios` Gradle project reads the selected backend through
`SqlContract` and translates its named scenarios into JDBC. Its launcher
projects configure either the Java agent or `opentelemetry-jdbc`. Vendor
directories contain the conformance configuration and coverage, so another
PostgreSQL client such as Vert.x SQL can sit beside JDBC without duplicating the
shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
