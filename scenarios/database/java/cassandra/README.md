# Cassandra conformance scenarios

Cassandra packages cover the Java agent's driver 3.x, driver 4.0-4.3, and
driver 4.4+ instrumentation paths. The driver 4.4+ package also runs the published
`opentelemetry-cassandra-4.4` library instrumentation. Earlier driver ranges are
agent-only because OpenTelemetry does not publish standalone instrumentation
for them.

| Package | Driver | Instrumentation |
| --- | --- | --- |
| `cassandra-driver-3` | DataStax 3.11.5 | Java agent |
| `cassandra-driver-4.3` | DataStax 4.3.1 | Java agent |
| `cassandra-driver-4.19` | Apache 4.19.3 | Java agent and library |

Renovate keeps the early DataStax driver below 4.4 so dependency updates retain
coverage of that instrumentation path. The version catalog pins each driver,
and Gradle discovers the shared workload and launcher projects automatically.

## Workloads and expectations

Each package runs four named scenarios using the
[shared Cassandra contract](../../contracts/cassandra.yaml):

| Scenario | Measured operation |
| --- | --- |
| `query` | Simple CQL query for an absent row |
| `prepared` | Prepared and bound CQL query for an absent row |
| `batch` | Two-statement logged batch with fixed IDs and values |
| `error` | Query against a missing table, rejected by Cassandra |

The shared driver 3 and driver 4 workloads contain no OpenTelemetry code.
Launchers choose the instrumentation. The library launcher passes the session's
original contact points to `CassandraTelemetry.wrap` so the instrumentation
can emit stable server address and port attributes.

The contract requires one Cassandra client span and
`db.client.operation.duration` for each operation. It allows optional Java SDK
and exporter self-metrics through `allowed_metrics`, without making the
operation-duration metric optional.

## Container and connection

The [database runner](../../../../tools/database/runner/README.md) starts one
pinned Cassandra 5.0.9 container per package. Its
[schema](../../../../tools/database/runner/src/database_conformance/cassandra.cql)
recreates the `conformance` keyspace and `items` table without seeding rows.
The fixed operations do not depend on package execution order.

The node uses `datacenter1`, one token, a 256 MB maximum heap, and a 64 MB young
generation. Cassandra's startup timeout defaults to 180 seconds; operators can
override it with `OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT`.

Packages map `DATABASE_HOST`, `DATABASE_PORT`, and
`DATABASE_LOCAL_DATACENTER` to `CASSANDRA_HOST`, `CASSANDRA_PORT`, and
`CASSANDRA_LOCAL_DATACENTER`. The datacenter variable is specific to Cassandra.
Authentication is disabled, so `DATABASE_USER` and `DATABASE_PASSWORD` are
empty for this backend.

Run one package from the repository root with Docker installed and running:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/cassandra/cassandra-driver-4.19/opentelemetry-library
```

The adjacent Java-agent package and the driver 3 and early driver 4 packages use
the same runner and contract.
