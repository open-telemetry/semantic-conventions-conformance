# Elasticsearch native instrumentation

The [native package](api-client/native-instrumentation) tests the latest stable
Elasticsearch Java API Client, currently
[9.5.5](https://github.com/elastic/elasticsearch-java/tree/v9.5.5).
It performs a match-all search through the
[shared launcher](../shared/elasticsearch/api-client-native).
The version catalog tracks only the current client generation, with no legacy
REST or Transport Client packages.

The client creates its own OpenTelemetry spans. The launcher supplies the
repository's [scenario SDK](../../../../tools/java/scenario-sdk) to the client's
`OpenTelemetryForElasticsearch` and flushes exports before shutdown.
No Java agent or external instrumentation library is attached.

`OTEL_SEMCONV_STABILITY_OPT_IN=database` enables the client's stable path
parameter attributes. The [search contract](../../contracts/elasticsearch-api-client.yaml)
requires one `CLIENT` span from the `elasticsearch-api` instrumentation scope,
with `db.system.name=elasticsearch`, `db.operation.name=search`, and
`db.operation.parameter.index=conformance`. It also checks the HTTP method,
successful response status, and server connection attributes on that span.
The native client emits no separate HTTP span or duration metrics.

The runner starts a digest-pinned Elasticsearch 9.5.5 node with security
disabled, waits for yellow cluster health, and creates the `conformance` index
from a [fixed mapping](../../../../tools/database/runner/src/database_conformance/elasticsearch.json).
The index has one shard, no replicas, and refreshes disabled; it contains no
seeded documents.

`DATABASE_HOST` and `DATABASE_PORT` identify the HTTP connection.
`DATABASE_USER` and `DATABASE_PASSWORD` are empty.

Run a package from the repository root after installing the runner and Java
support. Docker must be running:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/elasticsearch/api-client/native-instrumentation
```
