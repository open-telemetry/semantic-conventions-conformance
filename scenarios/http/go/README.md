# Go HTTP conformance scenarios

```text
<library>/scenarios/                what the client and server do, no OTel
<library>/<instrumentation>/<side>/
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
```

This directory is the Go build root for the HTTP domain, the way
[`java/`](../java) is the Gradle one. It is a single module, so one
`go build ./...` covers every scenario and one `go.sum` pins what they all
resolve to. The shared projects under [`tools/`](../../../tools) are reached
through `replace` directives rather than published versions, because they
belong to this repository: a scenario should measure the helper in the checkout
it was built from, not a release of it.

`net-http/scenarios/` is the workload, and it imports no OpenTelemetry at all.
The per-instrumentation `main` packages under `net-http/otelhttp/` are what
attach `otelhttp` and start the SDK, which is the same split Java uses — the
difference between two instrumentations of one library should be visible as the
code that differs, and nothing else.

Go's `main` package is a directory, so a launch package and its
`conformance.yaml` land in the same directory naturally, and `<side>` is that
directory rather than a name inside a build file.

## Routes

`net/http`'s `ServeMux` takes the method and the path template in the pattern
itself, so the contract's routes are declared in net/http's own model:

```go
mux.Handle("GET /users/{userId}", answer())
```

Nothing is attached per route. `ServeMux` records the pattern it matched on the
request. After the handler returns, `otelhttp` v0.70.0 uses that pattern for the
server span name and the metrics' `http.route`. It does not add `http.route` to
the server span: it records the span's request attributes before the mux
matches, and what it adds to the span afterwards is the status and the body
sizes.

## Running one

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/go
otel-conformance scenarios/http/go/net-http/otelhttp/client
otel-conformance scenarios/http/go/net-http/otelhttp/server
```

Every Go package is built and started the same way, so
[`otel-conformance-go`](../../../tools/go) holds that and a `conformance.yaml`
just names it. `setup:` compiles, and the measured `run:` is the resulting
binary rather than `go run`, which would compile on the clock and leave the
toolchain as the scenario's parent process.
