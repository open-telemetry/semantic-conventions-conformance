---
applyTo: "scenarios/**"
---

# Code rules for scenarios

- Run the domain's shared workload contract where one exists. Before calling missing telemetry an instrumentation gap, verify that the workload exercised the behavior that should produce it.
- Keep instrumentation setup out of shared workload code. Configure the instrumentation under test and any companion instrumentation it needs in the launcher or implementation environment.
- Each conformance directory commits the `data.json` produced by measuring its instrumentation.
