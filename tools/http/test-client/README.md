# HTTP conformance test client

The traffic and telemetry expectations for HTTP conformance scenarios. There
are two independent contracts in [`../contracts`](../contracts) — one per
instrumented side — and the runner injects the actions of whichever one a
package declares, so every language sends the same requests and the runner
checks each request independently.

## The contracts

[`client.yaml`](../contracts/client.yaml) says what an instrumented HTTP
client emits for each request it sends.
[`server.yaml`](../contracts/server.yaml) says what an instrumented HTTP
server emits for each request it answers. Neither refers to the other. They
happen to start from equivalent traffic, and nothing keeps them that way:
either can gain an action, drop one, or change an expectation on its own.

Each document has a contract-level `description`, a top-level `driver`, a
`readiness` exchange, and a `scenarios` list. Each scenario has a
human-readable `description`, an HTTP-specific `action`, and generic
telemetry under `expect`. `readiness` has the same `description` and
`action`, and no `expect`, because nothing measures it. Every language helper
needs it, so a contract without it fails to load:

```yaml
description: What an instrumented HTTP server emits for each request it answers.
driver: runner
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
            kind: SERVER
            attributes:
              http.request.method: GET
              http.response.status_code: 200
          expect:
            count: 1
      metrics: [http.server.request.duration]
      events: []
```

The runner expands each entry into one action with its own capture window and
report, and passes the action through `OTEL_CONFORMANCE_SCENARIO_ACTION` as
strict JSON. A one-shot client process decodes that object and sends only its
request, so two successful GETs cannot satisfy one aggregate count. The
package's single Weaver process receives all forwarded telemetry and produces
one result after the selected actions.

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

Each shape has its own contract, and the contract says who drives it.

A **server** scenario is a plain server process, in any language:

1. listen on the port in `OTEL_HTTP_SCENARIO_PORT`,
2. answer the exchanges through framework-native routes,
3. shut down when standard input closes — which is when its SDK flushes.

It never sends the requests itself. `otel-http-drive` does, from its own
process:

```yaml
scenario_contract: ../../../../../../tools/http/contracts/server.yaml
scenario_run: otel-http-drive --serve <the server scenario command>
```

That contract's `driver: runner` is what makes this persistent: it tells the
runner to drive one process through the whole batch, and the runner tells the
driver so through the environment. The package names a contract and a command,
and nothing about how it is run.

The driver picks a free port, starts the command, waits on the fixed readiness
request, sends the measured requests with the Python
standard library, then closes the command's standard input and exits with its
exit code. Driving from outside is what keeps a server run honest: no
instrumentation the scenario loads can reach the sender, so client spans it
never meant to produce cannot land in the report.

When the runner drives it, the driver starts one measured server process for
the selected batch and sends readiness once. It then sends one HTTP request
for each
action record from the runner. Every request carries exactly what the action
declares, plus the fixed `User-Agent` and, where there is a body,
`Content-Type`. The driver never adds a `traceparent`: a remote parent would
change what is under test, reparenting the server span, handing it a sampling
decision it did not make, and exercising context extraction the scenario never
asked for. The driver checks the response before it writes `action_complete`.

Startup first waits for the child to listen, then the driver sends the contract's
readiness exchange. The runner keeps that bootstrap telemetry outside the first
action, by its timestamps rather than by anything marking it. It advances only
after the driver acknowledges the response, expected telemetry arrives,
in-flight exports drain, and the action has stayed unchanged for the settle
period. Metric intervals must close within one action or the readiness window;
a point that crosses a response boundary fails instead of being assigned by
export order.

Every measured server and runner-managed mock server receives
`OTEL_CONFORMANCE_SCENARIO_ACTIONS` as canonical
JSON. It is an array of HTTP action objects, with readiness first and every
measured request and response after it. The runner parses the contract the
package declares and passes that table to the driver, which hands it on to the
measured server unchanged and drives readiness from it. A package pointing at
a contract of its own is therefore driven by that contract, not by whichever
one the driver's installation shipped. The driver falls back to its packaged
contract only when nothing gave it a table, which is how a server is driven by
hand. A table that is not a non-empty array of well-formed actions fails
before the measured server is started. `OTEL_HTTP_SCENARIO_PORT` remains the
selected listening port. When the runner closes the driver's stdin, the driver
closes the server's stdin, waits for its SDK to flush, writes `stopped`, and
returns the server's exit code.

The driver fails closed. A readiness or response mismatch, malformed or
out-of-sequence action, early child exit, or shutdown failure becomes an
`action_error` or a nonzero driver result. It sends no later HTTP actions after
an action error, and the runner marks the rest of the batch unexecuted.

A **client** scenario is the sender, so it decodes the runner-selected action
and sends that request with the library under test.
[`client.yaml`](../contracts/client.yaml)'s `driver: instrumentation` is what
makes it one-shot: the instrumented component initiates the action, so each
action gets its own process. The runner starts
[`http-mock-server`](../mock-server) for it, because the directory declares it
under `server:`, and publishes the base URL as `${MOCK_SERVER_URL}`. That mock
server answers the client contract's own injected exchanges, including its
readiness route, which is the one the runner polls before the first action:

```yaml
scenario_contract: ../../../../../../tools/http/contracts/client.yaml
scenario_run: node scenario.js
```

## Per language

Each language gets a small helper here to decode the injected JSON, look up
server answers, and decode one client action. None needs an HTTP client beyond
the one under test, and none reads YAML. The helpers consume JSON environment
handoffs; only the runner and `otel-http-drive` read a contract file, and
`otel-http-drive` reads the server contract because that is what it drives.

- [`python/`](python) — `otel_http_test_client`: the `otel-http-drive` command
  every language's server scenarios are driven by, `respond()` for answering
  concrete requests, and `serve()` for a Python server scenario.
- [`java/`](java) — `HttpContract` decodes the environment,
  `HttpServerWorkload.respond` looks up answers for any JVM framework, and
  `HttpClientWorkload.drive` sends the one selected request. Its unit tests
  drive both halves against each other. Client processes wait 100 milliseconds
  for asynchronous instrumentation callbacks before exiting.
- [`js/`](js) — three Node modules: `contract` decodes the environment,
  `respond` looks up answers for any Node framework, and `drive` sends one
  runner-selected request through a caller-supplied sender. Its unit tests
  drive both halves against each other.
- [`dotnet/`](dotnet) — `HttpContract` decodes the environment,
  `HttpServerWorkload.Respond` looks up answers for any .NET framework, and
  `HttpClientWorkload.DriveAsync` sends one runner-selected request through a
  caller-supplied sender. Its unit tests drive both halves against each other.
