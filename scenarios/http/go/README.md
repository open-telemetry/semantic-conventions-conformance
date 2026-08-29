# Go HTTP conformance scenarios

```text
<library>/scenarios/                what the client and server do, no OTel
<library>/<instrumentation>/<side>/
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
```

This directory is the Go build root for the HTTP domain. It is a single module,
so one `go build ./...` covers every scenario and one `go.sum` pins what they
all resolve to. The shared projects under [`tools/`](../../../tools) are
reached through `replace` directives rather than published versions, because
they belong to this repository: a scenario should measure the helper in the
checkout it was built from, not a release of it.

All Go modules in this repository require Go 1.25. Their current OpenTelemetry
dependencies require the same version, and CI selects the toolchain from this
directory's `go.mod`.

Each `<library>/scenarios/` package is the workload, and it imports no
OpenTelemetry. The per-instrumentation `main` packages attach `otelhttp`,
`otelecho`, `otelgin`, `otelmux`, or `otelrestful` and start the SDK. The
difference between instrumentations should be visible as the code that differs,
and nothing else.

Go's `main` package is a directory, so a launch package and its
`conformance.yaml` land in the same directory naturally, and `<side>` is that
directory rather than a name inside a build file.

## Routes

Every workload declares the contract's routes in its framework's native model.
For example, `net/http`'s `ServeMux` takes the method and path template in the
pattern itself:

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
otel-conformance scenarios/http/go/echo/otelecho/server
otel-conformance scenarios/http/go/gin/otelgin/server
otel-conformance scenarios/http/go/gorilla-mux/otelmux/server
otel-conformance scenarios/http/go/go-restful/otelrestful/server
```

Every Go package is built and started the same way, so
[`otel-conformance-go`](../../../tools/go) holds that and a `conformance.yaml`
just names it. `setup:` compiles, and the measured `run:` is the resulting
binary rather than `go run`, which would compile on the clock and leave the
toolchain as the scenario's parent process.
