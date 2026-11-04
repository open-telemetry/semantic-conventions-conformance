# MySQL JDBC scenarios

The database runner selects MySQL with `runner_config.backend: mysql` and starts
a pinned official MySQL container. It applies the
[scenario schema](../../../../tools/database/runner/src/database_conformance/mysql.sql)
before measured processes start. The schema creates the workload's empty table
and stored procedure without seeding rows. MySQL has a 120-second startup
timeout; `OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT` overrides it.

Both JDBC instrumentation modes use Connector/J with `openTelemetry=DISABLED`
so each package measures only its declared OpenTelemetry instrumentation.
MySQL client spans use `db.mysql.client`. Each SQL operation's action and
expected telemetry live together in the
[MySQL contract](../../../../tools/database/sql-test-client/contracts/mysql.yaml).

Run either package from the repository root after installing the
[runner and Java support](../README.md):

```sh
otel-conformance scenarios/database/java/mysql/jdbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/mysql/jdbc/opentelemetry-library
```
