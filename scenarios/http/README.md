# HTTP conformance scenarios

What HTTP instrumentations emit, checked against the
[HTTP semantic conventions][http] and recorded as committed coverage.

```text
<language>/<library>[/<side>]/<instrumentation>/
    conformance.yaml    how to run it
    requests.py         the program, when package-local
    pyproject.toml      Python dependencies, locked in uv.lock
    data.json           the coverage it produced, committed
```

Python currently has `python/flask/opentelemetry` (server) and
`python/httpx/opentelemetry` (client). Java has four isolated Armeria packages:
client and server coverage for both the OpenTelemetry Java agent and explicit
OpenTelemetry library instrumentation. The shared Java sources and locked
Gradle build live above those packages under `java/`.

Unlike [gen-ai](../gen-ai), the program sits with the implementation rather
than in a shared `scenarios/` directory when only one instrumentation uses it.
Armeria is shared because the same client and server programs compare two
instrumentation mechanisms.

## Both sides of the domain

[`otel-http-test-client`](../../tools/http/test-client) owns the request
sequence and the routes it assumes, so a client and a server are measured
against the same traffic.

A **server** scenario *is* the server, and emits nothing until something calls
it — so the program brings the app up and drives itself. A **client** scenario
is the sender: it hands its own library to the same driver, pointed at
[`http-mock-server`](../../tools/http/mock-server), which the runner starts
because the directory declares it under `server:`.

The routes are the test client's contract; an app that implements different
ones silently records less coverage rather than failing.

Client and server packages stay separate even when they use the same library
and instrumentation. Coverage reduces all telemetry in a package, so combining
both sides could hide an unexpected client span in a server run or the reverse.
The Java server driver therefore uses raw sockets rather than an instrumentable
HTTP client.

## Running one

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server
otel-conformance scenarios/http/python/flask/opentelemetry
otel-conformance scenarios/http/python/httpx/opentelemetry
otel-conformance scenarios/http/java/armeria/client/opentelemetry-javaagent
otel-conformance scenarios/http/java/armeria/client/opentelemetry-library
otel-conformance scenarios/http/java/armeria/server/opentelemetry-javaagent
otel-conformance scenarios/http/java/armeria/server/opentelemetry-library
```

Each Java package's `setup` uses the committed wrapper and dependency lock to
copy a stable classpath and pinned Java agent into `java/runtime/`. Its measured
`run` is a direct `java` process, not Gradle, so every scenario inherits the
fresh OTLP endpoint injected by the runner instead of a daemon's older
environment.

A finding weaver or a policy raises is a result, not a build break: CI runs
with `--report-only`. What must not change silently is `data.json`, which every
complete run rewrites and CI diffs. A divergence someone has looked at goes in
`expected_violations` with a reason; the Flask package records its known
missing `url.path` server attribute there.
See [`tools/runner/README.md`](../../tools/runner/README.md)
for the file format and [`../gen-ai/README.md`](../gen-ai/README.md) for why
these directories declare no span or metric expectations.

[http]: https://opentelemetry.io/docs/specs/semconv/http/
