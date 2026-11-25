---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

- Each shared GenAI workload file is named for one class defined in the scenario README and exercises exactly that class's documented exchange.
- Shared GenAI workload programs neither import OpenTelemetry nor name an instrumentation.
- GenAI scenarios record findings without declaring `expected_violations` or span, metric, or event expectations. A typed span match with no `expect` may classify a span the reduction cannot otherwise place.
