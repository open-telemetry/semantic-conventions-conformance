---
applyTo: "scenarios/database/java/**"
---

# Java database Gradle discovery

- Java database Gradle discovery prunes nested builds with their own settings files, dot-prefixed directories, and the `bin`, `build`, `buildSrc`, `node_modules`, `out`, `src`, and `target` trees. Build scripts beneath those paths do not declare conformance subprojects.
