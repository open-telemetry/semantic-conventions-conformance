---
applyTo: "scenarios/database/java/**"
---

# Code rules for Java database scenarios

- Java database targets place conformance configuration and coverage under `<backend>/<client>/<instrumentation>`. Keep reusable workloads and launchers under `shared/`, retaining the client level for client-specific code.
- Gradle discovery must not register nested builds or build files found in hidden directories or source fixtures as scenario subprojects.
