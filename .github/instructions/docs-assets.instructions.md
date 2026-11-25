---
applyTo: "docs/assets/**"
---

# Code rules for docs/assets

- The dashboard indexes signals by both type (`span`, `metric`, or `event`) and name, not by name alone or by span kind.

- The dashboard fails to load when declarations from different runners for the same signal type and name disagree on span kind or base attributes. Refinement attributes are not part of this comparison.
