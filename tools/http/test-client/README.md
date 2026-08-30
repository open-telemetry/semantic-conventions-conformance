# HTTP conformance test client

The traffic every HTTP conformance scenario is measured against, shared so the
coverage a client and a server produce is comparable.

[`contract.json`](contract.json) is where that traffic is written down, once.
Every language reads that file rather than restating it, so a scenario in the
eleventh language is measured against the same traffic as the first.
[`client-telemetry.yaml`](client-telemetry.yaml) separately declares the
telemetry every client implementation must emit for that traffic. The
conformance runner evaluates every language against the same expectations.

## The contract

`requests` is the concrete traffic sent in order, with each answer. It includes
readiness, a parameterized user path with and without a query string, a request
body, and two error statuses reached through the same path shape.

A server declares matching routes in its framework's native form. This is
intentionally not contract data: route builders, annotations, compile-time
routing, and Servlet mappings have different construction models and may
report different native templates. What they share is the concrete traffic
their routes must answer.

The requests are fixed, so their statuses and response bodies are constants.
Each request carries its answer literally. `${requestBody}` is the one
substitution, used to prove that a scenario read the body that arrived; there
is no path-parameter template language for every language to reimplement.

The document and each request carry a `description`. The top-level description
explains the contract, and each request's description says what it is in the
contract for and therefore what dropping it would stop measuring.

### Server responses are checked centrally

A server scenario declares routes in the framework under test — that
declaration is what an instrumentation reads a route from, so there is no
avoiding one implementation per framework. Everything downstream is shared:
an exact lookup by concrete method and path can supply the status and body. The
external driver checks every answer and fails the run if it disagrees.
Statuses are compared exactly; bodies are compared as parsed JSON, since
whitespace and key order are each language's JSON writer's business.

A client scenario consumes each response but does not implement that assertion
again. Its shared telemetry contract checks the five client spans centrally,
including their methods, response status, and URL.

## The two scenario shapes

A **server** scenario is a plain server process, in any language:

1. listen on the port in `OTEL_HTTP_SCENARIO_PORT`,
2. answer the exchanges through framework-native routes,
3. shut down when standard input closes — which is when its SDK flushes.

It never sends the requests itself. `otel-http-drive` does, from its own
process:

```yaml
scenarios:
  requests:
    run: otel-http-drive --serve <the server scenario command>
```

The driver picks a free port, starts the command, waits on the request marked
as readiness in the contract, sends the measured requests with the Python
standard library, then closes the command's standard input and exits with its
exit code. Driving from outside is what keeps a server run honest: no
instrumentation the scenario loads can reach the sender, so client spans it
never meant to produce cannot land in the report.

A **client** scenario is the sender, so it reads the contract and sends the
requests with the library under test. The runner starts
[`http-mock-server`](../mock-server) for it, because the directory declares it
under `server:`, and publishes the base URL as `${MOCK_SERVER_URL}`. That mock
server answers the same concrete exchanges from the same file, so a client is
measured against what a server scenario would have answered. Each client
package imports `client-telemetry.yaml`, so the runner—not its language
helper—checks what those requests emitted.

## Per language

Each language gets a small helper here—enough to read the contract, look up
server answers, and loop over measured client requests. No language restates
the traffic or validates client responses, and none needs an HTTP client of its
own beyond the one under test.

- [`python/`](python) — `otel_http_test_client`: the `otel-http-drive` command
  every language's server scenarios are driven by, `respond()` for answering
  concrete requests, and `serve()` for a Python server scenario.
- [`java/`](java) — `HttpContract` reads the file, `HttpServerWorkload.respond`
  looks up answers for any JVM framework, and `HttpClientWorkload.drive` sends
  the requests. The build copies `contract.json` onto the classpath, and its
  unit tests drive both halves against each other.
- [`js/`](js) — three Node modules: `contract` reads the file, `respond` looks
  up answers for any Node framework, and `drive` sends the requests through a
  caller-supplied sender. Its unit tests drive both halves against each other.
- [`dotnet/`](dotnet) — `HttpContract` reads the file,
  `HttpServerWorkload.Respond` looks up answers for any .NET framework, and
  `HttpClientWorkload.DriveAsync` sends the requests through a caller-supplied
  sender. The build embeds `contract.json` as a manifest resource, and its unit
  tests drive both halves against each other.
