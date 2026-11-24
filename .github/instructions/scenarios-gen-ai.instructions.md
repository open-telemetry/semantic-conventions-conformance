---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

- Give each documented GenAI scenario class its own file named for the class, and reuse that exchange across implementations of the same library. Keep the request shape and options comparable to other implementations of that class; document omissions imposed by the client API. A new class requires a matching scenario contract in the README.
- A GenAI workload does not import OpenTelemetry, name its instrumentation, or read its own configuration. Map `${MOCK_SERVER_URL}` to the client library's base-URL environment variable in `conformance.yaml`; only if the SDK has no such variable may the workload read the endpoint and pass it explicitly.
- A GenAI implementation environment contains only the instrumentation it measures. In JavaScript, the shared scenario package depends only on the client library and exports one async exchange per class; each implementation's class entry point invokes the matching exchange and owns instrumentation setup, with native telemetry registration allowed in a shared implementation-local `run.js`.
- GenAI scenarios record findings rather than assert or suppress them: do not declare `expected_violations` or span, metric, or event expectations. A documented span `match` with `type` but no `expect` may classify a span the reduction cannot otherwise place; it must leave the findings intact.
