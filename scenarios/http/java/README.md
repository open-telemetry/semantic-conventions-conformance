# HTTP conformance scenarios in Java

Java HTTP instrumentations, measured against
[the shared HTTP contract](../../../tools/http/test-client/contract.json).

Each `<library>/scenarios` project contains the workload. Its sibling
instrumentation projects launch that workload. The dependency versions are
pinned in [`gradle/libs.versions.toml`](gradle/libs.versions.toml).

`opentelemetry-javaagent` projects attach the full Java agent.
`opentelemetry-library` projects initialize the SDK and install one explicit
library instrumentation.

## Running one

Run a package from the repository root:

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/java
otel-conformance scenarios/http/java/okhttp/opentelemetry-javaagent/client
otel-conformance scenarios/http/java/tomcat/opentelemetry-javaagent/server
otel-conformance scenarios/http/java/okhttp/opentelemetry-library/client
otel-conformance scenarios/http/java/servlet/opentelemetry-library/server
```
