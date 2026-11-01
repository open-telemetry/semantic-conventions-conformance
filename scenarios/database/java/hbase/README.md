# HBase conformance scenarios

Both HBase client API lines run the shared workload through the OpenTelemetry
Java agent. The `hbase-1` package uses the 1.7.2 client and fixture; `hbase-2` uses
2.4.18. Renovate keeps clients within `>=1.7.2 <2.0.0` and `>=2.4.18 <2.5.0`,
the ranges covered by the agent's dedicated instrumentation. Fixture versions
and checksums in the [backend](../../../../tools/database/runner/src/database_conformance/_hbase.py)
are updated by hand.

Run either package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/hbase/hbase-1/opentelemetry-javaagent
otel-conformance scenarios/database/java/hbase/hbase-2/opentelemetry-javaagent
```

## Java toolchains

CI uses Java 25 for the Gradle build. The HBase workload, launchers, and shared
`scenario-support` and `agent-control` projects select Java 21 toolchains.
Gradle provisions that JDK when needed, and prepared HBase runtimes record
Java 21. Other database projects retain the Java 25 default.

The HBase clients' Hadoop dependencies call `Subject.getSubject`, which is no
longer supported on Java 24 and later. Compiling them on a newer JDK does not
make those dependencies compatible at runtime.

## Fixtures and workload

Docker must be running. Each session builds a local image from a SHA-512-verified
Apache HBase binary distribution and a digest-pinned Eclipse Temurin Java 8 base.
It starts the matching server API line, waits for readiness, then applies the
[initialization script](../../../../tools/database/runner/src/database_conformance/hbase.rb).
The script creates namespace `conformance`, table `items`, column family `data`,
and one row with key `seed` and `data:name=seed`. The session removes both its
container and local image on close. Startup failures include container logs.

HBase advertises fixed loopback ports 2181 for ZooKeeper, 16000 for the master,
and 16020 for the region server. Only one HBase conformance package can run on
a host at a time. The runner supplies `DATABASE_HOST` and `DATABASE_PORT` as the
ZooKeeper quorum and port; these fixtures use no client authentication.

The [shared workload](../shared/hbase/scenarios) imports no OpenTelemetry code.
Each operation runs in a separate process:

| Scenario | HBase client call | Workload |
| --- | --- | --- |
| `get` | `Table.get` | Verify the seeded row's value |
| `put` | `Table.put` | Write `put-row` with `data:name=put-value` |
| `scan` | `Table.getScanner` | Require at least one row |
| `batch` | `Table.batch` | Write two rows and reject per-row errors |

## Contracts and coverage

Both packages opt into stable database semantic conventions and share the
[HBase telemetry contract](../../contracts/hbase.yaml). The runner's registry
maps both backend selectors to system `hbase` and client span type
`db.hbase.client`.

The contract checks the measured Get, Mutate, Scan, or BATCH Mutate operation
and the metadata-table Scan. Batch spans must record a batch size of two.
The Java agent reports the ZooKeeper cluster key `127.0.0.1:2181:/hbase` as
`server.address`, without a separate `server.port`. Expectations check that
cluster address rather than the region-server RPC endpoint.

The packages retain committed coverage for both client lines. Metrics include
`db.client.operation.duration` and `queueSize`; contracts expect no events.
Runtime telemetry and log export are disabled because HBase client logging
activates SDK log-pipeline counters that may not export before these short-lived
processes exit.
