# Database conformance scenarios in Java

Java conformance for PostgreSQL, MariaDB, and HBase. JDBC is tested through
the OpenTelemetry Java agent and the OpenTelemetry JDBC library
instrumentation. HBase 1.x and 2.x client APIs are tested through the Java
agent.

The language-neutral SQL actions and telemetry expectations live together in
backend-specific files under
[`tools/database/sql-test-client/contracts`](../../../tools/database/sql-test-client/contracts).
The runner injects the selected action as JSON. The `shared:jdbc:scenarios`
Gradle project parses it through `SqlContract` and translates it into JDBC. Its
launcher projects configure either the Java agent or `opentelemetry-jdbc`.
Vendor directories contain the conformance configuration and coverage, so
another PostgreSQL client such as Vert.x SQL can sit beside JDBC without
duplicating the shared JDBC code.

The Java code only connects and performs measured operations. Database
lifecycle and schema creation stay in the Python runner, where later languages
can reuse them.

The HBase scenarios use the latest client in each API range covered by the
agent's dedicated instrumentation: 1.7.x and 2.4.x.
Use Java 25 for the Gradle build and keep `JAVA_HOME` on that JDK, matching CI.
The HBase workload, launchers, and their shared scenario-support and agent-control
projects select Java 21 toolchains; Gradle provisions that JDK when needed.
The prepared HBase runtimes record Java 21, while JDBC retains the Java 25
default. The HBase clients' Hadoop dependencies call `Subject.getSubject`,
which is no longer supported on Java 24 and later, so changing only the build
JDK would not make those dependencies compatible at runtime.

For both HBase client lines, the Java agent reports the ZooKeeper cluster key
(`127.0.0.1:2181:/hbase`) as `server.address`, with no separate `server.port`.
The shared contract checks that cluster address rather than the region-server
RPC endpoint. The committed coverage records the attributes CI observed.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running.
