---
applyTo: "scenarios/**/js/**,tools/js/**"
---

# Code rules for JavaScript scenarios and tooling

- A JavaScript scenario package that uses a helper package from `tools/` declares its own `file:` dependency on that helper rather than relying on a registry range satisfied by a sibling workspace. Implementation packages may depend on their own library's scenarios package with `"*"`.
