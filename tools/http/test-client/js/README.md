# HTTP conformance test client for Node

The two halves of [the contract](../README.md) a Node scenario needs: answering
a concrete request, and sending the measured ones.

```text
src/contract.js         decodes runner-injected JSON
src/server-workload.js  answers one concrete request
src/client-workload.js  sends one selected request
```

## Answering

`respond(method, target, requestBody)` is an exact lookup by concrete method
and path, so it is the same for Express as for any other framework. What is not
here is route _declaration_ — that is what an instrumentation reads `http.route`
from, so each framework declares its own routes and calls this to answer them.

`scenarioPort()` is the port the driver chose, which every server scenario binds
on `127.0.0.1`.

## Sending

`drive(baseUrl, send)` sends the request selected by
`OTEL_CONFORMANCE_SCENARIO_ACTION`. `send` is the call
being measured, so the library under test is the scenario's to choose:

```js
await drive(process.env.MOCK_SERVER_URL, async (method, url, body) => {
  const response = await undici.request(url, { method, body });
  return { status: response.statusCode, body: await response.body.text() };
});
```

Server helpers decode the complete action table from
`OTEL_CONFORMANCE_SCENARIO_ACTIONS`. The first entry is readiness. The package
reads no YAML and discovers no contract file.

Each client process handles one action and exits. A measured server decodes the
action table once, stays up for the selected batch, and receives the requests
sequentially from the external driver.
