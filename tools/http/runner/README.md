# HTTP conformance

Runs a conformance directory against the [HTTP semantic conventions][http],
with the upstream registry and the coverage reduction already wired in.

```sh
pip install -e tools/runner -e tools/http/runner
http-conformance path/to/directory
```

A directory declaring `runner: http-conformance` gets the same wiring from
plain `otel-conformance` and from `pytest`. See
[`tools/runner/README.md`](../../runner/README.md) for what a conformance
directory contains and how to write one.

The package is a [`Domain`](../../runner/README.md#wrapping-it-for-your-repo)
and three things:

| | |
| --- | --- |
| [`versions.env`](src/http_conformance/versions.env) | which release of `open-telemetry/semantic-conventions` a run validates against. The weaver pin is shared, in the runner |
| [`_coverage.py`](src/http_conformance/_coverage.py) | how to recognise an HTTP span: `http.request.method` identifies one, and the kind says which of the two types it is |
| [`policies/`](src/http_conformance/policies) | what weaver can't check itself — the attributes each span type must carry, and the span name |

Weaver validates every attribute it *sees* against the registry, but it never
matches a span to a span definition, so it can't report a missing one. That is
what the policy file is for. It flags `required` attributes, and the subset of
`recommended` an instrumentation can always set — not the ones the registry
records at that level but whose prose makes them conditional
(`http.request.resend_count` on a retry, `user_agent.original` when the client
sent the header), which would blame the instrumentation for the request it was
given.

The span-name policy checks the HTTP method token separately from its target.
When a server span name has a target but no `http.route`, it reports
`http_route_not_present`: without the matched route, the policy can't verify
that the target has bounded cardinality.

Span status and `error.type` aren't checked here: neither is HTTP-specific, so
both live in [the runner's own policies](../../runner/README.md#advice-policies).

Both sides measure the same action catalog in
[`contract.yaml`](../test-client/contract.yaml), and each package selects the
variant naming its own side. The variant declares who drives the exchange,
which is what decides how the package runs.

Client scenarios select `client`, whose `instrumentation` role starts a
one-shot process per contract entry from that entry's JSON action, each with
one capture window and report. They call
[`http-mock-server`](../mock-server), which installs with this package.
Server scenarios select `server`, whose `runner` role has them driven from
outside by [`otel-http-drive --serve`](../test-client), with
one measured server process per selected batch and the action table handed off
as JSON. The runner invokes Weaver once for the package.

The persistent driver sends readiness and then one request per action, in
sequence and never concurrently. It stamps each exchange where it sent the
request and where it saw the answer. The runner isolates an action from the
timestamps the instrumentation itself reported, then waits for expected
telemetry, forwarding drains, and a quiet settle period before sending the
next request. Nothing is injected into the traffic under test. Ambiguous
metric intervals, telemetry that arrives after its action was sealed, and
driver protocol failures fail the package rather than falling back to an
aggregate report.

[http]: https://opentelemetry.io/docs/specs/semconv/http/
