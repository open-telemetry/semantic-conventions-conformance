# Database conformance scenarios in Java

Java database conformance for PostgreSQL and MariaDB JDBC, plus PostgreSQL
R2DBC. Each client is tested through the OpenTelemetry Java agent and the
matching OpenTelemetry library instrumentation.

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

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-library
```

Docker must be installed and running.
