# HTTP conformance scenarios in Java

Java HTTP instrumentations, measured against
[the shared HTTP contract](../../../tools/http/test-client/contract.json).

Each `<library>/scenarios` project contains the workload. Its sibling
instrumentation projects launch that workload. The dependency versions are
pinned in [`gradle/libs.versions.toml`](gradle/libs.versions.toml).

Java agent scenarios run with the full agent. Their span expectations also
match the instrumentation scope, so a span from an underlying library cannot
stand in for the instrumentation under test. A test-only agent extension
exposes the scope name to the runner as `otel.scope.name`, which the runner
consumes rather than recording as HTTP coverage. A scenario disables another
instrumentation only when it would otherwise create the span first. The
Armeria server disables Netty, Restlet disables the JDK HTTP server, and
Servlet disables Tomcat.

## Running one

Run a package from the repository root:

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/java
otel-conformance scenarios/http/java/okhttp/opentelemetry-javaagent/client
otel-conformance scenarios/http/java/tomcat/opentelemetry-javaagent/server
```
