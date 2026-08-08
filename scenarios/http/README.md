# HTTP conformance scenarios

What HTTP instrumentations emit, checked against the
[HTTP semantic conventions][http] and recorded as committed coverage.

```
<language>/<library>/<instrumentation>/
    conformance.yaml    how to run it
    requests.py         the program
    pyproject.toml      what it runs against, locked in uv.lock
    data.json           the coverage it produced, committed
```

Today that is `python/flask/opentelemetry` (server) and
`python/httpx/opentelemetry` (client).

Unlike [gen-ai](../gen-ai), the program sits with the implementation rather
than in a shared `scenarios/` directory: there is one instrumentation per
library here, so there is nobody to share it with. The `<instrumentation>`
level stays because a second one — a different vendor, an older release — is
what these files are shaped to be compared against, and when that happens the
program moves up a level.

## Both sides of the domain

[`otel-http-test-client`](../../tools/http/test-client) owns the request
sequence and the routes it assumes, so a client and a server are measured
against the same traffic.

A **server** scenario *is* the server, and emits nothing until something calls
it — so the program brings the app up and drives itself. A **client** scenario
is the sender: it hands its own library to the same driver, pointed at
[`http-mock-server`](../../tools/http/mock-server), which the runner starts
because the directory declares it under `server:`.

The routes are the test client's contract; an app that implements different
ones silently records less coverage rather than failing.

## Running one

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server
otel-conformance scenarios/http/python/flask/opentelemetry
otel-conformance scenarios/http/python/httpx/opentelemetry
```

A finding weaver or a policy raises is a result, not a build break: CI runs
with `--report-only`. What must not change silently is `data.json`, which every
complete run rewrites and CI diffs. A divergence someone has looked at goes in
`expected_violations` with a reason; neither directory declares any yet — the
Flask run reports contrib not setting `url.path` on a server span.
See [`tools/runner/README.md`](../../tools/runner/README.md)
for the file format and [`../gen-ai/README.md`](../gen-ai/README.md) for why
these directories declare no span or metric expectations.

[http]: https://opentelemetry.io/docs/specs/semconv/http/
