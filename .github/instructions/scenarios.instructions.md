---
applyTo: "scenarios/**"
---

# Code rules for scenarios

- Run the domain's shared workload contract where one exists. Before calling missing telemetry an instrumentation gap, verify that the workload exercised the behavior that should produce it.
- Each conformance directory commits the `data.json` produced by measuring its instrumentation.
