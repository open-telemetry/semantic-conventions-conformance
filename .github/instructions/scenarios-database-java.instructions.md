---
applyTo: "scenarios/database/java/**"
---

# Code rules for scenarios/database/java

- Java database instrumentation packages retain the backend, client, and instrumentation levels in their package paths; the corresponding shared launcher paths and Gradle project names retain those same levels.
- Gradle scenario discovery excludes nested builds, dot-prefixed directories, and source, dependency, and generated-output trees.
