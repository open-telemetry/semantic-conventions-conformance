# HTTP conformance test client for Go

`httpcontract` reads [`contract.json`](../contract.json), looks up its answers
for any Go framework, and drives the measured requests through a client
scenario's own library.

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
sender as a function so the requests leave the library being measured.

Standard library only, so importing it next to a scenario drags no dependency
into a run.

## Finding the contract

Java copies `contract.json` onto the classpath and Python installs it beside
its package. Go has neither, and `//go:embed` cannot reach outside the package
directory it appears in — so rather than commit a second copy of the traffic,
this package finds the one copy at run time, searching upwards from the working
directory for `tools/http/test-client/contract.json`. That is the scenario
directory under the runner and the package's own directory under `go test`,
both inside a checkout. `OTEL_HTTP_CONTRACT` names the file outright, for a
binary run somewhere else.

## Tests

`go test ./...` drives both halves against each other: `Drive` sends the
contract and `Respond` answers it, so the two sides are checked against the
file rather than against each other's assumptions.
