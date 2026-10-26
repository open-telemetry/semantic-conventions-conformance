# Database conformance scenarios in Java

Java scenarios share workloads and launchers under `shared/`. The Gradle
settings discover projects from build files in this scenario tree; tools shared
with other domains remain explicitly mapped in
[`settings.gradle.kts`](settings.gradle.kts). Build all Java database projects
from the repository root with:

```sh
scenarios/database/java/gradlew --project-dir scenarios/database/java build
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

Run one package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running. Redis connection tests also use Docker and
prepared scenario runtimes:

```sh
python -m pytest tools/database/runner/tests/test_redis_clients.py
```
