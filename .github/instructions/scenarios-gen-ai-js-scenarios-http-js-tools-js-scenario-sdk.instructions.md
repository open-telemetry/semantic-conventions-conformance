---
applyTo: "scenarios/gen-ai/js/**,scenarios/http/js/**,tools/js/scenario-sdk/**"
---

# Code rules for scenarios/gen-ai/js, scenarios/http/js, tools/js/scenario-sdk

- Node instrumentations that patch on module load are registered before the workload first loads the library under test. Pass `runScenario` a function that defers that load and execution; an already-started promise or a top-level import of the instrumented library defeats the ordering.
