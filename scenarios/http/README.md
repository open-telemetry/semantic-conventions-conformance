# HTTP conformance scenarios

What HTTP instrumentations emit, checked against the
[HTTP semantic conventions][http] and recorded as committed coverage.

```text
<language>/<library>/<instrumentation>/<side>/
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
rust/<library>/<instrumentation>/<side>/
    Cargo.toml          the measured binary package
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
```

A language that needs a build of its own has a build root directly under this
one: Java's version-pinned Gradle build, described below,
[`js/`](js/README.md), whose README explains the npm workspace it roots, and
[`rust/`](rust/README.md), whose README explains the Cargo workspace it roots.

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

In Rust the split is between crates. Its plain workload crates hold Actix
Web's native routes and the awc request sequence without importing
OpenTelemetry. The instrumentation-specific binary crates install
`opentelemetry-instrumentation-actix-web` around those workloads. One Cargo
workspace at `rust/` includes the shared crates under `tools/` and commits one
lockfile for all of them.

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

A Python instrumentation has nothing to build. Its workload is a module in
`python/<library>/scenarios/`, and each `<side>/` directory holds the
`pyproject.toml` and `uv.lock` that pin one instrumentation, next to the
`scenario.py` that turns it on before handing the workload to the harness.

## The scenario contract

[`contract.json`](../../tools/http/test-client/contract.json) is the concrete
traffic every HTTP scenario is measured against, written down once and read by
every language, so a client's and a server's coverage are comparable. The
document and each request carry a `description`; each request's description
says what it is in the sequence for and what dropping it would stop measuring.

| Request | What it is there for |
| --- | --- |
| `GET /health` | Readiness only. Sent before the sequence, never measured. |
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

It is checked, not just written down. Statuses are compared exactly and bodies
as parsed JSON, since whitespace and key order are each language's JSON
writer's business. A scenario that disagrees fails the run rather than quietly
recording coverage that cannot be compared with the rest.

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
  -e tools/http/test-client/python -e tools/java -e tools/js -e tools/rust
otel-conformance scenarios/http/java/armeria/opentelemetry-javaagent/client
otel-conformance scenarios/http/java/armeria/opentelemetry-javaagent/server
otel-conformance scenarios/http/java/armeria/opentelemetry-library/client
otel-conformance scenarios/http/java/armeria/opentelemetry-library/server
otel-conformance scenarios/http/js/express/opentelemetry-express/server
otel-conformance scenarios/http/js/undici/opentelemetry-undici/client
otel-conformance scenarios/http/python/flask/opentelemetry-flask/server
otel-conformance scenarios/http/python/requests/opentelemetry-requests/client
otel-conformance scenarios/http/rust/awc/opentelemetry-actix-web/client
otel-conformance scenarios/http/rust/actix-web/opentelemetry-actix-web/server
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

Rust separates the build from the measured run. `otel-conformance-rust build`
compiles the current package in release mode, then `otel-conformance-rust run`
starts the workspace's absolute release binary path. Cargo is not the measured
process's parent, and the same package declaration works on Windows because
the launcher adds `.exe` there.

A finding weaver or a policy raises is a result, not a build break: CI runs
with `--report-only`. What must not change silently is `data.json`, which every
complete run rewrites and CI diffs. A divergence someone has looked at goes in
`expected_violations` with a reason.
See [`tools/runner/README.md`](../../tools/runner/README.md)
for the file format.

[http]: https://opentelemetry.io/docs/specs/semconv/http/
