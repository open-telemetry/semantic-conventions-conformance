# HTTP conformance scenarios in Java

Java HTTP instrumentations, measured against
[the shared HTTP contract](../../../tools/http/test-client/contract.json).

Each library has a directory with a package for every side it supports. All
libraries are covered by the OpenTelemetry Java agent. The dependency versions
are pinned together in
[`gradle/libs.versions.toml`](gradle/libs.versions.toml).

**Clients:** Apache HttpAsyncClient, Apache HttpClient, Armeria, Async HTTP
Client, HttpURLConnection, Java HTTP Client, Jetty HttpClient, Jodd HTTP,
Netty, OkHttp, Ratpack, Reactor Netty, Spring WebFlux, Vert.x HTTP Client.

**Servers:** Akka HTTP, Armeria, Grizzly, Helidon, Java HTTP Server, JAX-RS,
Netty, Pekko HTTP, Ratpack, Restlet, Servlet, Spring Web MVC, Spring WebFlux,
Tomcat, Undertow, Vert.x Web.

Libraries such as Netty and Spring WebFlux have separate client and server
packages. JAX-RS resources and Servlets run in embedded Tomcat, but each package
measures the instrumentation it names rather than the underlying server.

## Running one

Run a package from the repository root:

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/java
otel-conformance scenarios/http/java/okhttp/opentelemetry-javaagent/client
otel-conformance scenarios/http/java/tomcat/opentelemetry-javaagent/server
```
