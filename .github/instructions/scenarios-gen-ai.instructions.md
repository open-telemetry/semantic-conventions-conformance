---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

- GenAI scenarios must not declare `expected_violations` or span, metric, or event expectations. A span the reduction cannot place may use a `match` with `type` but no `expect`, leaving all findings recorded.
