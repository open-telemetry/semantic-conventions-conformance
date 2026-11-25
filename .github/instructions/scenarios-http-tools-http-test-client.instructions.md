---
applyTo: "scenarios/http/**,tools/http/test-client/**"
---

# Code rules for scenarios/http, tools/http/test-client

- HTTP workloads use the shared contract's concrete exchanges, statuses, and response bodies, with `${requestBody}` as the only response-body substitution. Servers declare corresponding routes through their framework's native routing model rather than taking route templates from the contract.
