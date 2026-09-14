# Database conformance scenarios in Java

Java database conformance covers PostgreSQL and MariaDB JDBC plus Cassandra
driver 3.x and 4.x. JDBC runs through the OpenTelemetry Java agent and JDBC
library instrumentation. Cassandra runs every supported agent API line and the
standalone driver 4.4+ instrumentation library.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

The Cassandra packages pin one current driver in each instrumentation range:
3.11.5 for driver 3, 4.3.1 for the early driver 4 API, and Apache driver 4.19.3
for driver 4.4 and later. Each of the four packages runs query, prepared,
batch, and server-error operations against its own disposable Cassandra node.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
