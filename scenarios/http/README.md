# HTTP conformance scenarios

What HTTP instrumentations emit, checked against the
[HTTP semantic conventions][http] and recorded as committed coverage.

```text
<language>/<library>/<instrumentation>/<side>/
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
```

A language that needs a build of its own has a build root directly under this
one: the version-pinned Gradle build under `java/` and the solution under
`dotnet/`, both described below, and [`js/`](js/README.md), whose README
explains the npm workspace it roots.

An instrumentation's directory holds everything about it, the way a gen-ai
one holds its `pyproject.toml` beside its `conformance.yaml`. For Java that is
the Gradle project that builds its `main` classes, while `scenarios/` holds
what both of them run — the same sharing `gen-ai/python/<library>/scenarios/`
has, where one program is run by every instrumentation of that library:

```text
java/armeria/scenarios/                  what the client and server do, no OTel
java/armeria/opentelemetry-javaagent/    build.gradle.kts, src/, client/, server/
java/armeria/opentelemetry-library/      build.gradle.kts, src/, client/, server/
```

The `main` classes are per instrumentation because attaching library
instrumentation is code rather than a command-line flag; everything they do
beyond that is in `scenarios/`.

Armeria therefore has four isolated packages: client and server coverage for
both the OpenTelemetry Java agent and explicit OpenTelemetry library
instrumentation. Client and server stay separate packages because coverage
reduces everything a package emitted, so combining them could hide a client
span in a server run. The Gradle project paths follow the directories, so a
`conformance.yaml` names `armeria:opentelemetry-javaagent` and a second
library's own projects cannot be confused with it.

The traffic is shared because both mechanisms measure the same Armeria
behavior. Bootstrap and runtime classpaths are not: the agent launchers use
plain Armeria and attach the agent, while the library launchers use the shared
[`scenario-sdk`](../../tools/java/scenario-sdk) project for SDK lifecycle and
install their framework-specific decorators. The version-pinned Gradle build
they all belong to is rooted at `java/`, which also pulls in the projects
under [`tools/java`](../../tools/java) that any domain's scenarios share.

[`dotnet/`](dotnet) measures one mechanism: an ASP.NET Core server package and
a `System.Net.Http.HttpClient` client package, each with a `scenarios/` project
holding what it does and a launcher project holding the instrumentation. Its
solution also lists the shared projects under
[`tools/dotnet`](../../tools/dotnet).

A Python instrumentation has nothing to build. Its workload is a module in
`python/<library>/scenarios/`, and each `<side>/` directory holds the
`pyproject.toml` and `uv.lock` that pin one instrumentation, next to the
`scenario.py` that turns it on before handing the workload to the harness.

## The scenario contract

[`contract.yaml`](../../tools/http/test-client/contract.yaml) combines each
client request and response with its telemetry expectations. The runner turns
every list entry into a separate scenario, while language helpers select the
same entry through `OTEL_CONFORMANCE_SCENARIO_INDEX`. This keeps the traffic
shared without aggregating independent requests into one report.

| Request | What it is there for |
| --- | --- |
| `GET /health` | Readiness only. It is not a contract-list scenario. |
| `GET /users/123` | A parameterized route, so `http.route` is the template rather than the concrete path. |
| `GET /users/123?fields=name&verbose=true` | A query string, which is `url.query` and must not leak into `http.route`, `url.path` or the span name. |
| `POST /items` | A non-GET carrying a body. The answer echoes it, so a scenario that never read the body fails. |
| `GET /status/404` | A 4xx: `error.type` and `http.response.status_code`, on the span and the duration metric. |
| `GET /status/500` | A 5xx, which some instrumentations treat differently from a 4xx. |

The requests are fixed, so their statuses and bodies are constants — each entry
carries its answer literally, and `${requestBody}` is the one substitution. A
server declares matching routes in its framework's native form, which is
deliberately not contract data: route builders, annotations, compile-time
routing and Servlet mappings have different construction models and may report
different native templates. What they share is the concrete traffic those
routes must answer.

Server responses are checked centrally by `otel-http-drive`: statuses exactly
and bodies as parsed JSON, since whitespace and key order are each language's
JSON writer's business. Client conformance is decided by the common telemetry
contract instead.

See [`tools/http/test-client`](../../tools/http/test-client) for the per-
language helpers that read it.

## Both sides of the domain

A **server** scenario is a plain server process: it binds the port
`otel-http-drive` chose, answers the routes, and shuts down when the driver
closes its standard input. The driver sends the requests from outside, so a
server run records server telemetry only — no instrumentation the scenario
loads can reach the sender. A **client** scenario is the sender: it reads the
same contract and sends it with the library under test, pointed at
[`http-mock-server`](../../tools/http/mock-server), which the runner starts
because the directory declares it under `server:`.

Client and server packages stay separate even when they use the same library
and instrumentation. Coverage reduces all telemetry in a package, so combining
both sides could hide an unexpected client span in a server run or the reverse.

## Running one

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/python -e tools/java -e tools/js \
  -e tools/dotnet
otel-conformance scenarios/http/java/armeria/opentelemetry-javaagent/client
otel-conformance scenarios/http/java/armeria/opentelemetry-javaagent/server
otel-conformance scenarios/http/java/armeria/opentelemetry-library/client
otel-conformance scenarios/http/java/armeria/opentelemetry-library/server
otel-conformance scenarios/http/js/express/opentelemetry-express/server
otel-conformance scenarios/http/js/http/opentelemetry-http/client
otel-conformance scenarios/http/js/http/opentelemetry-http/server
otel-conformance scenarios/http/js/undici/opentelemetry-undici/client
otel-conformance scenarios/http/dotnet/aspnetcore/opentelemetry-aspnetcore/server
otel-conformance scenarios/http/dotnet/httpclient/opentelemetry-http/client
otel-conformance scenarios/http/python/aiohttp/opentelemetry-aiohttp-client/client
otel-conformance scenarios/http/python/aiohttp/opentelemetry-aiohttp-server/server
otel-conformance scenarios/http/python/asgi/opentelemetry-asgi/server
otel-conformance scenarios/http/python/django/opentelemetry-django/server
otel-conformance scenarios/http/python/falcon/opentelemetry-falcon/server
otel-conformance scenarios/http/python/fastapi/opentelemetry-fastapi/server
otel-conformance scenarios/http/python/flask/opentelemetry-flask/server
otel-conformance scenarios/http/python/httpx/opentelemetry-httpx/client
otel-conformance scenarios/http/python/pyramid/opentelemetry-pyramid/server
otel-conformance scenarios/http/python/requests/opentelemetry-requests/client
otel-conformance scenarios/http/python/starlette/opentelemetry-starlette/server
otel-conformance scenarios/http/python/tornado/opentelemetry-tornado/server
otel-conformance scenarios/http/python/urllib/opentelemetry-urllib/client
otel-conformance scenarios/http/python/urllib3/opentelemetry-urllib3/client
otel-conformance scenarios/http/python/wsgi/opentelemetry-wsgi/server
```

Every Java package is built and started the same way, so
[`otel-conformance-java`](../../tools/java) holds the toolchain and a
`conformance.yaml` names its Gradle launch project and main class, plus whether
the JVM should attach an agent. A mechanism only needs packages for the
capabilities it supports; it does not need a dual-mode executable.

`otel-conformance-java prepare` uses the committed wrapper and version-pinned
dependency declarations to copy the resolved classpath and Java agent into
`java/build/scenario-runtime/`. Its measured `run` is a direct `java`
process, not Gradle, so every scenario inherits the fresh OTLP endpoint
injected by the runner instead of a daemon's older environment.

[`otel-conformance-dotnet`](../../tools/dotnet) needs no arguments at all: a
scenario directory sits inside the project that produces it, so `build`
publishes that project and `run` starts what it published from
`dotnet/artifacts/scenario-runtime/`. A `conformance.yaml` therefore names
neither a configuration nor an assembly path.

A finding weaver or a policy raises is a result, not a build break: CI runs
with `--report-only`. What must not change silently is `data.json`, which every
complete run rewrites and CI diffs. A divergence someone has looked at goes in
`expected_violations` with a reason.
See [`tools/runner/README.md`](../../tools/runner/README.md)
for the file format.

[http]: https://opentelemetry.io/docs/specs/semconv/http/
