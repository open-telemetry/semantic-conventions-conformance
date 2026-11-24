---
applyTo: "scenarios/browser/**,scenarios/database/**,scenarios/gen-ai/**,scenarios/http/**"
---

# Code rules for scenarios/browser, scenarios/database, scenarios/gen-ai, scenarios/http

- When multiple instrumentations measure the same library behavior, reuse the workload and keep telemetry setup in the implementation-specific entry point or agent. Shared HTTP workload code does not depend on OpenTelemetry, and an out-of-process OBI target runs without an in-process SDK or agent.
