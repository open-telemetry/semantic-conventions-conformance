---
applyTo: "scenarios/http/go/**,scenarios/http/java/**,tools/obi/**"
---

# Code rules for scenarios/http/go, scenarios/http/java, tools/obi

- An OBI scenario runs the same uninstrumented workload as the other implementations for its library, with no SDK or agent in the measured process; OBI wraps the run command and instruments from outside.
