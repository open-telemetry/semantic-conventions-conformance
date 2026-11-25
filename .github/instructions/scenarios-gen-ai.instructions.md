---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

- Each documented GenAI class has a separate workload file named for the class that performs exactly its defined exchange, including the request options that exercise telemetry.
- GenAI configurations declare neither `expected_violations` nor span, metric, or event expectations. A commented span `match` with `type` and no `expect` is allowed only when coverage reduction cannot classify the span on its own, and it leaves findings intact.
