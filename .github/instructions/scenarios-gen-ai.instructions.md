---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

- Give each GenAI library a scenario for every README class its client API supports, even if the instrumentation does not cover that class. Use one file named for each class, perform exactly the exchange defined in the README, and supply the corresponding request options wherever the client API can express them. Do not add an unlisted class without defining it in the README first.
- GenAI workloads use the client SDK's base-URL environment variable mapped from `${MOCK_SERVER_URL}` in `conformance.yaml` and read no configuration of their own. If the SDK lacks that setting, the workload reads the mapped endpoint and passes it to the client.
- GenAI conformance YAML declares neither `expected_violations` nor span, metric, or event expectations. An active span `match` carrying `type` but no accompanying `expect` is allowed only when the reducer cannot classify the span on its own. Explain the need in a comment, leave all findings intact, and remove the match once the span identifies itself.
- Enable GenAI message-content capture consistently for the whole implementation directory, never per scenario, using the instrumentation's configuration unless it captures content unconditionally. This lets the run measure content on spans and on the `gen_ai.client.inference.operation.details` event without mixing capture modes in the directory's coverage union.
- Keep only the instrumentation under test in each GenAI implementation environment. Disable client-native OpenTelemetry when measuring a separate instrumentation, and keep it enabled when measuring the native implementation.
