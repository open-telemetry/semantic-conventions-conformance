# Database conformance scenarios in Java

Java database instrumentations, beginning with JDBC through the OpenTelemetry
Java agent and the PostgreSQL backend managed by the database runner.

The `jdbc:scenarios` Gradle project owns the instrumentation-independent
workload. Its `jdbc:opentelemetry-javaagent` sibling supplies the Java agent and
launches that workload.

The Java code only connects and performs measured operations. PostgreSQL
lifecycle and schema creation stay in the Python database runner so later
languages can use the same backend.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
