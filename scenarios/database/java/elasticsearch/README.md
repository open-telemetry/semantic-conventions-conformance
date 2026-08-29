# Elasticsearch Java-agent scenarios

Each client has a separate Gradle launcher under
[`shared/elasticsearch/`](../shared/elasticsearch) so its dependency graph stays
isolated. These scenarios measure Java-agent instrumentation, not the Java API
Client's native OpenTelemetry instrumentation.

| Scenario package | Client | Version | Operation |
| --- | --- | --- | --- |
| `rest/opentelemetry-javaagent` | Low Level REST Client | 7.17.29 | `_count` |
| `api-client/opentelemetry-javaagent` | Elasticsearch Java API Client | 7.17.19 | `search` |
| `transport/opentelemetry-javaagent` | Transport Client | 7.17.29 | `prepareSearch` |

The [client-specific contracts](../../contracts) contain only telemetry
expectations. Each package declares its named scenario and client-specific run
command in `conformance.yaml`.

The Java API Client stays at 7.17.19 because 7.17.20 introduced native
OpenTelemetry instrumentation. The Low Level REST Client shares its 7.17 version
with the Transport Client artifacts, which end on that line. Elasticsearch 8
dropped the transport protocol, so the container also stays below 8.

The runner starts a digest-pinned Elasticsearch 7.17.29 node with security
disabled, waits for yellow cluster health, and creates the `conformance` index
from a [fixed mapping](../../../../tools/database/runner/src/database_conformance/elasticsearch.json).
The index has one shard, no replicas, and refreshes disabled; it contains no
seeded documents.

`DATABASE_HOST` and `DATABASE_PORT` identify the HTTP connection.
`DATABASE_TRANSPORT_PORT` is a separately published port for the Transport
Client. `DATABASE_USER` and `DATABASE_PASSWORD` are empty.

Run a package from the repository root after installing the runner and Java
support. Docker must be running:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/elasticsearch/rest/opentelemetry-javaagent
otel-conformance scenarios/database/java/elasticsearch/api-client/opentelemetry-javaagent
otel-conformance scenarios/database/java/elasticsearch/transport/opentelemetry-javaagent
```
