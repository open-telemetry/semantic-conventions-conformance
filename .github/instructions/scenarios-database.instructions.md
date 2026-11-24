---
applyTo: "scenarios/database/**"
---

# Code rules for scenarios/database

- Within the Java database build, place conformance packages at `<system>/<client>/<instrumentation>`. Keep reusable workloads and launchers under `java/shared/`, retaining the client level for code specific to that client.
- Java database Gradle discovery includes projects with `build.gradle` or `build.gradle.kts` and prunes nested builds, dot-prefixed directories, and `bin`, `build`, `buildSrc`, `node_modules`, `out`, `src`, and `target` trees. Map shared tooling outside the scenario tree explicitly.
- The shared MongoDB span contract neither requires nor forbids `db.query.text` or `db.query.summary`, because the pinned MongoDB span conventions do not define them. Do not record their absence as a coverage gap or assert driver-internal command serialization.
