# HTTP conformance test client for Go

`httpcontract` decodes the runner-supplied actions, looks up answers for any Go
framework, and drives one selected request through a client scenario's own
library.

```text
Exchanges(), Requests()   the traffic, in order
Respond(...)              what a server scenario answers
ScenarioPort()            the port otel-http-drive chose
Drive(...), Verify(...)   what a client scenario sends, and the check on it
```

A server scenario declares routes in the framework under test, because that
declaration is what an instrumentation reads `http.route` from. Everything
downstream is shared: `Respond` is an exact lookup by concrete method and path,
so every Go framework agrees on the statuses and bodies. `Drive` takes the
progress output as an `io.Writer` and the sender as a function, so callers
control the logs and requests leave the library being measured.

Clients read `OTEL_CONFORMANCE_SCENARIO_ACTION`. Servers parse
`OTEL_CONFORMANCE_SCENARIO_ACTIONS` once and reuse the table for route lookups.

## Tests

`go test ./...` drives both halves against the same injected action data.
