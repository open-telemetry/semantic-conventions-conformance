---
applyTo: "scenarios/http/**"
---

# Code rules for scenarios/http

- HTTP workloads use the shared contract's concrete requests, statuses, and response bodies, with `${requestBody}` as the only body substitution. Servers declare matching routes in their framework's native form rather than taking route templates from the contract.
