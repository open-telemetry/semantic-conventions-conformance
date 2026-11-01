# Database conformance scenarios in Java

Java scenarios share workloads and launchers under `shared/`. The Gradle
settings discover projects from build files in this scenario tree; tools shared
with other domains remain explicitly mapped in
[`settings.gradle.kts`](settings.gradle.kts). Build all Java database projects
from the repository root with:

```sh
scenarios/database/java/gradlew --project-dir scenarios/database/java build
```

Discovery prunes nested builds with their own settings files, dot-prefixed
directories, and `bin`, `build`, `buildSrc`, `node_modules`, `out`, `src`, and
`target` trees. Build files inside source fixtures or generated output do not
become subprojects.

Project-discovery integration tests require a JDK and run separately from the
Python unit suite. CI runs them on Linux after setting up Java and Gradle.
To run them locally from the repository root:

```sh
OTEL_CONFORMANCE_TEST_JAVA_DISCOVERY=1 python -m pytest tools/database/runner/tests/test_java_project_discovery.py
```

JDBC packages use the shared SQL workload and its
[backend-specific action and telemetry contracts](../../../tools/database/sql-test-client/README.md).
Their shared launchers exercise either the OpenTelemetry Java agent or JDBC
library instrumentation. A package directory holds its conformance
configuration, so another client can reuse the workload without duplicating
JDBC code.

Redis clients reuse a common workload and can be run with Java-agent or supported
library instrumentation. The
[Redis workload guide](shared/redis/README.md) documents its commands,
connection settings, and client-specific telemetry. SQL Server's container and
JDBC prerequisites are documented in its
[scenario notes](sql_server/README.md).

MongoDB covers the latest stable synchronous and Reactive Streams drivers
with both Java-agent and published standalone library instrumentation. Its
[workload guide](shared/mongodb/README.md) and
[backend notes](mongodb/README.md) describe commands, connection settings, and
bootstrap.

Run one package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/sync/opentelemetry-javaagent
```

Docker must be installed and running. Redis connection tests also use Docker and
prepared scenario runtimes:

```sh
python -m pytest tools/database/runner/tests/test_redis_clients.py
```
