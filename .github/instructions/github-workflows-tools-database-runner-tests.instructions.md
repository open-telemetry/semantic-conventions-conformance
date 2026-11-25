---
applyTo: ".github/workflows/**,tools/database/runner/tests/**"
---

# Code rules for .github/workflows, tools/database/runner/tests

- Database project-discovery tests that run Gradle belong to the opt-in Java integration suite, not the default Python unit suite, and their CI job provisions Java and Gradle.
