---
applyTo: "scenarios/database/**,tools/database/sql-test-client/**"
---

# Code rules for shared SQL workloads

- For workloads using the shared SQL contracts, language helpers read the selected JSON action from `OTEL_CONFORMANCE_SCENARIO_ACTION` and translate it into client API calls without reloading the contract.
