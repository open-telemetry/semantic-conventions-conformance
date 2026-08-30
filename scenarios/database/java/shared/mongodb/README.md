# MongoDB workload

The synchronous, legacy asynchronous, and Reactive Streams drivers each run
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

The legacy async driver is pinned to its final release, 3.12.14. That API is
unmaintained and was replaced by Reactive Streams. The modern sync and Reactive
Streams drivers share a version because they are released together.

See the [backend notes](../../mongodb/README.md) for connection settings,
bootstrap, and package commands.
