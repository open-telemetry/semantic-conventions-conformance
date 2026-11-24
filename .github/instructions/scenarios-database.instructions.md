---
applyTo: "scenarios/database/**"
---

# Code rules for scenarios/database

- Java database targets place conformance configuration and coverage under `<backend>/<client>/<instrumentation>`. Keep reusable workloads and launchers under `shared/`, retaining the client level for client-specific code.
- Java database Gradle discovery must not register nested builds or build files found in hidden directories, source fixtures, dependencies, or generated output as scenario subprojects.
