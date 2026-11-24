---
applyTo: ".github/workflows/**,tools/database/**"
---

# Code rules for .github/workflows, tools/database

- Java database project-discovery tests that invoke real Gradle builds are opt-in integration tests. They skip in the default Python suite and run separately where a JDK and Gradle are available.
