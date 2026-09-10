# HTTP conformance test client for Node

The two halves of [the contract](../README.md) a Node scenario needs: answering
a concrete request, and sending the measured ones.

```text
src/contract.js         reads contract.yaml
src/server-workload.js  answers one concrete request
src/client-workload.js  sends one selected request
```

The only dependency is the YAML parser used before the measured request.

## Answering

`respond(method, target, requestBody)` is an exact lookup by concrete method
and path, so it is the same for Express as for any other framework. What is not
here is route _declaration_ — that is what an instrumentation reads `http.route`
from, so each framework declares its own routes and calls this to answer them.

`scenarioPort()` is the port the driver chose, which every server scenario binds
on `127.0.0.1`.

## Sending

`drive(baseUrl, send)` sends the request selected by
`OTEL_CONFORMANCE_SCENARIO_INDEX`. `send` is the call
being measured, so the library under test is the scenario's to choose:

```js
await drive(process.env.MOCK_SERVER_URL, async (method, url, body) => {
  const response = await undici.request(url, { method, body });
  return { status: response.statusCode, body: await response.body.text() };
});
```

## Finding the contract

`contract.yaml` is one directory above this package, and npm packs only a
package's own directory. Rather than generating a copy into the source tree,
the lookup walks up from this module until it finds the file at its place in
the repository. That works both where this package lives and where npm
installed a copy of it.
