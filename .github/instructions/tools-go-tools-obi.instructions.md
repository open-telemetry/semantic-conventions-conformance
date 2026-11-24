---
applyTo: "tools/go/**,tools/obi/**"
---

# Code rules for tools/go, tools/obi

- An OBI workload waiting at the gate starts only after explicit release following attachment; EOF alone does not release it. Tie cleanup of both the privileged OBI process and the workload's separate process group to launcher lifetime, including abrupt launcher death.
