# Cassandra conformance scenarios

The `java-driver` packages test only the latest stable Apache Cassandra Java
driver, pinned to `org.apache.cassandra:java-driver-core:4.19.4` in the
[version catalog](../gradle/libs.versions.toml). Both the Java agent and published
`opentelemetry-cassandra-4.4` library instrumentation use that same client.
The instrumentation artifact's `4.4` suffix identifies its compatibility API
boundary, not the driver version under test.

Renovate updates the single client pin. Gradle discovers the shared workload
and launcher projects automatically.

## Workloads and expectations

Each package runs four named scenarios using the
[shared Cassandra contract](../../contracts/cassandra.yaml):

| Scenario | Measured operation |
| --- | --- |
| `query` | Simple CQL query for an absent row |
| `prepared` | Prepared and bound CQL query for an absent row |
| `batch` | Two-statement logged batch with fixed IDs and values |
| `error` | Query against a missing table, rejected by Cassandra |

The shared workload contains no OpenTelemetry code. Launchers choose the
instrumentation. The library launcher passes the session's
original contact points to `CassandraTelemetry.wrap` so the instrumentation
can emit stable server address and port attributes.

The contract requires one Cassandra client span and
`db.client.operation.duration` for each operation, with no events. The
[shared Java Weaver configuration](../../../../tools/java/weaver.toml) filters
findings for optional SDK and exporter self-metrics.

## Container and connection

The [database runner](../../../../tools/database/runner/README.md) starts one
pinned Cassandra 5.0.9 container per package. Its
[schema](../../../../tools/database/runner/src/database_conformance/cassandra.cql)
recreates the `conformance` keyspace and `items` table without seeding rows.
The fixed operations do not depend on package execution order.

The node uses `datacenter1`, one token, a 256 MB maximum heap, and a 64 MB young
generation. Cassandra's startup timeout defaults to 180 seconds. Set
`OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT` in the runner's environment to
override it. The shared database lifecycle reads this override, not the package
or workload environment.

Packages map `DATABASE_HOST`, `DATABASE_PORT`, and
`DATABASE_LOCAL_DATACENTER` to `CASSANDRA_HOST`, `CASSANDRA_PORT`, and
`CASSANDRA_LOCAL_DATACENTER`. The datacenter variable is specific to Cassandra.
Authentication is disabled, so `DATABASE_USER` and `DATABASE_PASSWORD` are
empty for this backend.

Run one package from the repository root with Docker installed and running:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/cassandra/java-driver/opentelemetry-library
```

The adjacent Java-agent package uses the same client, runner, and contract.
