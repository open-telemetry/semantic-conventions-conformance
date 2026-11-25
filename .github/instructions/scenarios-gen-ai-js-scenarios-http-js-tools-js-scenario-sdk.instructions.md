---
applyTo: "scenarios/gen-ai/js/**,scenarios/http/js/**,tools/js/scenario-sdk/**"
---

# Code rules for scenarios/gen-ai/js, scenarios/http/js, tools/js/scenario-sdk

- For Node instrumentation that patches modules on load, `runScenario` receives a deferred workload function that loads the library under test only after instrumentation registration.
