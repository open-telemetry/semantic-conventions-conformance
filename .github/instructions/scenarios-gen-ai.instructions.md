---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

- Each documented GenAI scenario class has one workload file named for the class, and that file performs exactly the exchange defined for it in the GenAI README.
- GenAI package configuration maps `${MOCK_SERVER_URL}` to the client library's base-URL environment variable. If the client has no such setting, the workload reads the configured URL and passes it explicitly; it reads no unrelated configuration.
- Each GenAI implementation environment contains only the instrumentation it measures.
- GenAI configurations record findings without `expected_violations` or span, metric, or event expectations. A documented span `match` with `type` and no `expect` is allowed only when the reducer cannot classify the span on its own.
