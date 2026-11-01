# HBase conformance scenarios

The latest stable `org.apache.hbase:hbase-client` runs the shared workload with
HBase's own OpenTelemetry instrumentation against a matching fixture. No Java
agent or external HBase instrumentation is attached. The client and
fixture are pinned to 3.0.0, the highest stable release in
[Maven Central](https://repo.maven.apache.org/maven2/org/apache/hbase/hbase-client/maven-metadata.xml)
and an [official Apache distribution](https://downloads.apache.org/hbase/3.0.0/).
Fixture versions and Apache SHA-512 checksums in the
[backend](../../../../tools/database/runner/src/database_conformance/_hbase.py)
are updated together with the client.

Run the package from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/hbase/native
```

## Native SDK integration

The [native launcher](native/src/main/java/HbaseNativeScenario.java) initializes
the repository's `ScenarioSdk` before opening an HBase connection. SDK
autoconfiguration registers its result as `GlobalOpenTelemetry`, which HBase's
`TraceUtil.getGlobalTracer()` uses with scope `org.apache.hbase` and client version
`3.0.0`. The runner supplies a fresh OTLP endpoint for each measured process.

The workload closes its table and connection before the SDK flushes traces,
logs, then metrics and shuts down. Log export is disabled. The prepared
application classpath contains HBase 3.0.0, the OpenTelemetry SDK and OTLP exporter,
but no agent or external HBase instrumentation. The shared launcher plugin copies
an unused agent-control support jar outside that classpath; native commands never
attach it.

## Java toolchains

CI uses Java 25 for the Gradle build. The HBase workload, launcher, and shared
`scenario-support` and `scenario-sdk` projects select Java 21 toolchains.
Gradle provisions that JDK when needed, and prepared HBase runtimes record
Java 21. Other database projects retain the Java 25 default.

HBase 3 requires Java 17 or later. Its Hadoop 3.4 dependencies run on the
Java 21 toolchain used by the conformance package.

## Fixtures and workload

Docker must be running. Each session builds a local image from a SHA-512-verified
Apache HBase binary distribution and a digest-pinned Eclipse Temurin Java 17 base.
It starts the matching server, waits for readiness, then applies the
[initialization script](../../../../tools/database/runner/src/database_conformance/hbase.rb).
The script creates namespace `conformance`, table `items`, column family `data`,
and one row with key `seed` and `data:name=seed`. The session removes both its
container and local image on close. Startup failures include container logs.

HBase advertises fixed loopback ports 2181 for ZooKeeper, 16000 for the master,
and 16020 for the region server. Only one HBase conformance package can run on
a host at a time. The runner supplies `DATABASE_HOST` and `DATABASE_PORT` as
`HBASE_BOOTSTRAP_SERVERS` for the client's RPC connection registry on port 16000.
These fixtures use no client authentication.

The [shared workload](../shared/hbase/scenarios) imports no OpenTelemetry code.
Each operation runs in a separate process:

| Scenario | HBase client call | Workload |
| --- | --- | --- |
| `get` | `Table.get` | Verify the seeded row's value |
| `put` | `Table.put` | Write `put-row` with `data:name=put-value` |
| `scan` | `Table.getScanner` | Require at least one row |
| `batch` | `Table.batch` | Write two rows and reject per-row errors |

## Contracts and coverage

The package checks the emitted telemetry against stable database semantic
conventions using the [HBase telemetry contract](../../contracts/hbase.yaml).
The runner's registry
maps backend selector `hbase` to system `hbase` and client span type
`db.hbase.client`.

The contract requires stable database CLIENT spans for GET, PUT, SCAN, or BATCH
and the metadata-table SCAN, with namespace and collection attributes. Batch
spans must record a batch size of two. The bootstrap address is `127.0.0.1` with
`server.port=16000`. It also requires `db.client.operation.duration`, the SDK's
`queueSize` infrastructure metric, and no events.

## Observed native gaps

All four workloads complete successfully and emit their corresponding native
CLIENT span under `org.apache.hbase` version `3.0.0`. Strict conformance fails:

- The native table spans use legacy `db.system`, `db.name`, `db.operation`,
  `db.connection_string`, and `db.user`, not stable `db.system.name`,
  `db.namespace`, `db.collection.name`, `db.operation.name`, and server attributes.
  They do not satisfy the stable database CLIENT span expectations.
- HBase emits no `db.client.operation.duration`. The captured metrics describe
  SDK/exporter health, not database operations.
- The native scope has no schema URL. Weaver also reports deprecated RPC/network
  attributes, unregistered `db.hbase.table`, `db.hbase.regions`, and
  `db.hbase.container_operations`, and
  instrumentation setting status OK on successful spans.

No native findings are waived or filtered out. The package reuses the shared
Java Weaver configuration for SDK infrastructure findings only.
The committed [coverage](native/data.json) comes from fresh native-only runs.
Stable database span and metric coverage is empty; entity coverage and the real
findings remain recorded. Raw per-workload reports are written under
`native/output/weaver-reports/` when running the command above.

The four workloads each have four expectation failures. Strict runs also report
52 violations for GET, 52 for PUT, 47 for SCAN, and 53 for BATCH. CI's
`--report-only` mode downgrades semantic violations, but not missing expectations,
so this package still exits nonzero and fails the conformance job.
