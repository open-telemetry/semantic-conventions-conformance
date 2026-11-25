---
applyTo: "scenarios/browser/js/**,scenarios/gen-ai/js/**,scenarios/http/js/**"
---

# Code rules for scenarios/browser/js, scenarios/gen-ai/js, scenarios/http/js

- JavaScript scenario packages declare the shared tooling they use under `tools/` as local `file:` dependencies installed as copies, not symlinks or registry dependencies. Packages within the same scenario workspace can use workspace resolution.
