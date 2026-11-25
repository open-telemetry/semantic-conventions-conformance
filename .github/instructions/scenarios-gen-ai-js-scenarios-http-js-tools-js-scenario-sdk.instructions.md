---
applyTo: "scenarios/gen-ai/js/**,scenarios/http/js/**,tools/js/scenario-sdk/**"
---

# Code rules for scenarios/gen-ai/js, scenarios/http/js, tools/js/scenario-sdk

- Node entry points for patch-on-load instrumentation pass a deferred workload function to `runScenario` and load the client or framework only after instrumentation registration; deferring execution without deferring the relevant imports is insufficient.
