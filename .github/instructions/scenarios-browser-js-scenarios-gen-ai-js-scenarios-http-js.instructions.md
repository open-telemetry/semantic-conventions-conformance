---
applyTo: "scenarios/browser/js/**,scenarios/gen-ai/js/**,scenarios/http/js/**"
---

# Code rules for scenarios/browser/js, scenarios/gen-ai/js, scenarios/http/js

- JavaScript scenario packages declare dependencies on shared packages under `tools/` with explicit local `file:` references rather than relying on a registry version or a sibling package's install.
