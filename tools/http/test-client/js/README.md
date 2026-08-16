# HTTP conformance test client for Node

The two halves of [the contract](../README.md) a Node scenario needs: answering
a concrete request, and sending the measured ones.

```text
src/contract.js         reads contract.json
src/server-workload.js  answers one concrete request
src/client-workload.js  sends the measured requests and checks every answer
```

No dependencies at all, deliberately: a third-party HTTP client would be
instrumented alongside a scenario and its spans would land in the report.

## Answering

`respond(method, target, requestBody)` is an exact lookup by concrete method
and path, so it is the same for Express as for any other framework. What is not
here is route _declaration_ — that is what an instrumentation reads `http.route`
from, so each framework declares its own routes and calls this to answer them.

`scenarioPort()` is the port the driver chose, which every server scenario binds
on `127.0.0.1`.

## Sending

`drive(baseUrl, send)` sends the measured requests in order and checks every
answer. `send` is the call being measured, so the library under test is the
scenario's to choose:

```js
await drive(process.env.MOCK_SERVER_URL, async (method, url, body) => {
  const response = await undici.request(url, { method, body });
  return { status: response.statusCode, body: await response.body.text() };
});
```

Statuses are compared exactly; bodies are compared as parsed JSON, since
whitespace and key order are the JSON writer's business rather than the
contract's.

## Finding the contract

`contract.json` is one directory above this package, and npm packs only a
package's own directory. Rather than generating a copy into the source tree —
which is what the Python wheel and the Java jar each carry — the lookup walks up
from this module until it finds the file at its place in the repository. That
works both where this package lives and where npm installed a copy of it.
