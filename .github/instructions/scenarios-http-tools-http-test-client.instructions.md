---
applyTo: "scenarios/http/**,tools/http/test-client/**"
---

# Code rules for scenarios/http, tools/http/test-client

- HTTP workloads use the shared contract's concrete requests and prescribed response statuses and bodies, with `${requestBody}` as the only response substitution. Servers declare route templates through their framework's native routing model, not in the shared contract.
