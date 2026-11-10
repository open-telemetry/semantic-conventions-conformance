# HTTP conformance scenarios in Java

Java HTTP instrumentations, measured against
[the shared HTTP contract](../../../tools/http/test-client/contract.yaml).

Each `<library>/scenarios` project contains the workload. Its sibling
instrumentation projects launch that workload. The dependency versions are
pinned in [`gradle/libs.versions.toml`](gradle/libs.versions.toml).

`opentelemetry-javaagent` projects attach the full Java agent.
`opentelemetry-library` projects initialize the SDK and install one explicit
library instrumentation. `obi` projects install nothing: they wait at
[`otel-conformance-obi`](../../../tools/obi)'s gate, and OBI instruments them
from outside.

OBI reads route templates from the Spring annotations on the classpath, so the
Spring WebFlux and Spring Web MVC `obi` packages report the declared routes.
It has no route support for the other servers here, which declare their routes
in code, so for them it falls back to a route derived from the request path
(`/users/*`, `/status/*`). That is OBI's default, `routes.unmatched:
heuristic`, and it is what those baselines record. It does not follow semconv,
which says `http.route` must not be populated when it is not known and the
span name should then be just the method; OBI behaves that way with
`routes.unmatched: unset`.

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
```

An `obi` package runs only on Linux with BTF, as root or with passwordless
`sudo`; see [`otel-conformance-obi`](../../../tools/obi).
