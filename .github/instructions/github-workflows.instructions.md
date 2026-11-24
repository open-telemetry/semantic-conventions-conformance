---
applyTo: ".github/workflows/**"
---

# Code rules for .github/workflows

- Keep the semantic-convention registry cache key independent of the OBI release pin. An OBI-only version or digest change must not invalidate cached registries.
