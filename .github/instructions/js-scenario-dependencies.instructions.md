---
applyTo: "scenarios/browser/js/**,scenarios/gen-ai/js/**,scenarios/http/js/**"
---

# JavaScript scenario dependencies

- JavaScript scenario packages use checkout-relative `file:` dependencies for unpublished tools outside their npm workspace. This does not require `file:` for sibling packages resolved within the same workspace.
