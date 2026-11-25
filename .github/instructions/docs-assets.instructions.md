---
applyTo: "docs/assets/**"
---

# Code rules for docs/assets

- The dashboard indexes signals by both type (`span`, `metric`, or `event`) and name, not by name alone or by span kind. Conflicting declarations from different runners for the same type and name cause loading to fail rather than using one declaration to compare both targets.
