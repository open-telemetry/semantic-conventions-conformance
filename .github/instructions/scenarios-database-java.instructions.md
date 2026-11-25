---
applyTo: "scenarios/database/java/**"
---

# Code rules for scenarios/database/java

- Java database Gradle discovery prunes nested builds with their own settings files, dot-prefixed directories, and the `bin`, `build`, `buildSrc`, `node_modules`, `out`, `src`, and `target` trees. Build scripts beneath those paths do not declare conformance subprojects.
