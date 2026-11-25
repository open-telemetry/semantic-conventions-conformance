---
applyTo: "scenarios/database/java/**"
---

# Code rules for scenarios/database/java

- Database Gradle discovery skips nested builds with their own settings files, dot-prefixed directories, and `bin`, `build`, `buildSrc`, `node_modules`, `out`, `src`, and `target` trees. Build files in those trees do not become scenario subprojects.
