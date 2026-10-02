# Database conformance scenarios in Java

Java JDBC conformance for PostgreSQL and MariaDB, tested through the OpenTelemetry
Java agent and the OpenTelemetry JDBC library instrumentation. Elasticsearch
conformance covers the 7.17 Low Level REST Client, Java API Client, and Transport
Client through the Java agent.

The `shared:jdbc:scenarios` Gradle project owns the
instrumentation-independent workload. Its launcher projects configure either
the Java agent or `opentelemetry-jdbc`. Vendor directories contain the
conformance configuration and coverage, so another PostgreSQL client such as
Vert.x SQL can sit beside JDBC without duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

The Elasticsearch launchers are separate Gradle projects. This keeps each
client's dependency graph isolated while all three use the same 7.17.29
Elasticsearch container and deterministic `conformance` index. The API Client
uses 7.17.19, the last release in that line before native instrumentation.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/elasticsearch/rest/opentelemetry-javaagent
```

Docker must be installed and running.
