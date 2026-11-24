# HTTP conformance scenarios in Java

Java HTTP instrumentations, measured against
[the shared HTTP contract](../../../tools/http/test-client/contract.yaml).

Each `<library>/scenarios` project contains the workload. Its sibling
instrumentation projects launch that workload. The dependency versions are
pinned in [`gradle/libs.versions.toml`](gradle/libs.versions.toml).

`opentelemetry-javaagent` projects attach the full Java agent.
`opentelemetry-library` projects initialize the SDK and install one explicit
library instrumentation. `obi` projects install nothing: they run the
workload class itself, which waits at
[`otel-conformance-obi`](../../../tools/obi)'s gate, and OBI instruments them
from outside.

OBI can read route templates from the Spring annotations on the classpath, so
the Spring WebFlux and Spring Web MVC `obi` packages may report the declared
routes. For the other servers here, OBI does not read the routes declared in
code, including the `/users/*` and `/status/*` mappings in Tomcat and Grizzly.
See the [shared OBI configuration](../../../tools/obi/README.md#configuration)
for what spans and metrics report when OBI doesn't know the route.

`servlet` has no `obi` package: OBI's Java agent injection can deadlock the
servlet scenario at startup
([opentelemetry-ebpf-instrumentation#4244](https://github.com/open-telemetry/opentelemetry-ebpf-instrumentation/issues/4244)).

## Running one

Run a package from the repository root:

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/java -e tools/obi
otel-conformance scenarios/http/java/okhttp/opentelemetry-javaagent/client
otel-conformance scenarios/http/java/tomcat/opentelemetry-javaagent/server
otel-conformance scenarios/http/java/okhttp/opentelemetry-library/client
otel-conformance scenarios/http/java/servlet/opentelemetry-library/server
otel-conformance scenarios/http/java/tomcat/obi/server
otel-conformance scenarios/http/java/okhttp/obi/client
```

An `obi` package runs only on Linux with BTF, as root or with passwordless
`sudo`; see [`otel-conformance-obi`](../../../tools/obi).
