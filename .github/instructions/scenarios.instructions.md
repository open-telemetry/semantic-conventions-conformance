---
applyTo: "scenarios/**"
---

# Code rules for scenarios

- Implementations that exercise the same client or framework reuse the same workload. The workload does not select or configure the instrumentation that measures it.
- Each conformance directory commits the `data.json` produced by running its declared scenarios. The file records actual emissions and findings rather than hand-edited results.
