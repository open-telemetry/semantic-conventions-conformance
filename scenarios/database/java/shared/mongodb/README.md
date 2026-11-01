# MongoDB workload

The synchronous and Reactive Streams drivers each run
the same operations through Java-agent and published `opentelemetry-mongo-3.1`
library instrumentation. Workload projects perform database operations without
importing OpenTelemetry; launcher projects configure instrumentation.

| Scenario | MongoDB command |
| --- | --- |
| `find` | `find` by `_id` |
| `update` | `updateOne` by `_id` |
| `delete` | `deleteOne` by `_id` |
| `aggregate` | one-stage `$match` aggregation |

Packages share named telemetry expectations in
[`contracts/mongodb.yaml`](../../../contracts/mongodb.yaml), with driver-specific
run commands. Each expectation also accounts for the driver's `endSessions`
command when the client closes. MongoDB instrumentation does not currently emit
`db.query.summary`; expectations assert that gap.

Standalone library launchers pass the driver's configured seed addresses to
`MongoTelemetry.createCommandListener` so `server.address` and `server.port`
describe the same target as the Java-agent runs.

Both drivers use the latest stable client release, currently
[5.14.0](https://github.com/mongodb/mongo-java-driver/releases/tag/r5.14.0).
They share a version because they are released together.

See the [backend notes](../../mongodb/README.md) for connection settings,
bootstrap, and package commands.
