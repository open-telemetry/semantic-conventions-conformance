---
applyTo: "tools/obi/**,tools/runner/**"
---

# Code rules for tools/obi, tools/runner

- Timeout and settle durations read from the environment must be finite and non-negative. Reject `NaN` and infinities before computing deadlines; accept zero where the setting permits it.
