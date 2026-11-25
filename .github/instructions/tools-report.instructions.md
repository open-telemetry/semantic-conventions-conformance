---
applyTo: "tools/report/**"
---

# Code rules for tools/report

- Coverage scores use only `required` and unconditional `recommended` attributes, scored separately. `conditionally_required_conditional`, `recommended_conditional`, and `opt_in` remain visible as per-signal counts but do not enter either score.
