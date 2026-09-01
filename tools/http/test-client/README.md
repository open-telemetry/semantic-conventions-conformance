# HTTP conformance test client

The traffic and client telemetry expectations for HTTP conformance scenarios.
Every language reads [`contract.yaml`](contract.yaml), so clients send the same
requests and the runner checks each request independently.

## The contract

The document has a contract-level `description`, a `readiness` exchange, and a
`scenarios` list. Each scenario has a human-readable `description`, an
HTTP-specific `action`, and generic telemetry under `expect`. `readiness` has
the same `description` and `action`, and no `expect`, because nothing measures
it. Every language helper needs it, so a contract without it fails to load:

```yaml
description: Shared HTTP client requests and expected telemetry.
readiness:
  description: Checks whether the server is ready.
  action:
    request:
      method: GET
      path: /health
    response:
      status: 200
      body: '{"ok": true}'
scenarios:
  - description: Sends a request with a query string.
    action:
      request:
        method: GET
        path: /users/123?fields=name&verbose=true
      response:
        status: 200
        body: '{"id": 123, "name": "Alice"}'
    expect:
      spans:
        - match:
            kind: CLIENT
            attributes:
              http.request.method: GET
              http.response.status_code: 200
          expect:
            count: 1
            attributes:
              url.full:
                present: true
      events: []
```

The runner expands each entry into a separate scenario and passes its ordinal
through `OTEL_CONFORMANCE_SCENARIO_INDEX`. The language helper selects that
entry and sends only its request. A fresh weaver report checks one request, so
the two successful GETs cannot satisfy one aggregate count even though they
share the same method and status.

A server declares matching routes in its framework's native form. This is
intentionally not contract data: route builders, annotations, compile-time
routing, and Servlet mappings have different construction models and may
report different native templates. What they share is the concrete traffic
their routes must answer.

The requests are fixed, so their statuses and response bodies are constants.
`${requestBody}` in a response inserts the body that arrived. The `readiness`
exchange is declared beside the measured `scenarios` rather than in them, so
`GET /health` is never measured.

### Server responses are checked centrally

A server scenario declares routes in the framework under test — that
declaration is what an instrumentation reads a route from, so there is no
avoiding one implementation per framework. Everything downstream is shared:
an exact lookup by concrete method and path can supply the status and body. The
external driver checks every answer and fails the run if it disagrees.
Statuses are compared exactly; bodies are compared as parsed JSON, since
whitespace and key order are each language's JSON writer's business.

The mock server also answers 400 when the contract's POST body does not arrive,
so a client cannot pass by sending an empty body.

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

The driver picks a free port, starts the command, waits on the fixed readiness
request, sends the measured requests with the Python
standard library, then closes the command's standard input and exits with its
exit code. Driving from outside is what keeps a server run honest: no
instrumentation the scenario loads can reach the sender, so client spans it
never meant to produce cannot land in the report.

A **client** scenario is the sender, so it reads the runner-selected contract
entry and sends that request with the library under test. The runner starts
[`http-mock-server`](../mock-server) for it, because the directory declares it
under `server:`, and publishes the base URL as `${MOCK_SERVER_URL}`. That mock
server answers the same concrete exchanges from the same file, so a client is
measured against what a server scenario would have answered. Each client
package points `scenario_contract` at `contract.yaml` and declares one
`scenario_run` command.

## Per language

Each language gets a small helper here to read the contract, look up server
answers, and select one client request. None needs an HTTP client beyond the one
under test.

- [`python/`](python) — `otel_http_test_client`: the `otel-http-drive` command
  every language's server scenarios are driven by, `respond()` for answering
  concrete requests, and `serve()` for a Python server scenario.
- [`java/`](java) — `HttpContract` reads the file, `HttpServerWorkload.respond`
  looks up answers for any JVM framework, and `HttpClientWorkload.drive` sends
  the one selected request. The build copies `contract.yaml` onto the classpath,
  and its unit tests drive both halves against each other. Client processes
  wait 100 milliseconds for asynchronous instrumentation callbacks before
  exiting.
- [`js/`](js) — three Node modules: `contract` reads the file, `respond` looks
  up answers for any Node framework, and `drive` sends one runner-selected
  request through a caller-supplied sender. Its unit tests drive both halves
  against each other.
- [`dotnet/`](dotnet) — `HttpContract` reads the file,
  `HttpServerWorkload.Respond` looks up answers for any .NET framework, and
  `HttpClientWorkload.DriveAsync` sends one runner-selected request through a
  caller-supplied sender. The build embeds `contract.yaml` as a manifest
  resource, and its unit tests drive both halves against each other.
