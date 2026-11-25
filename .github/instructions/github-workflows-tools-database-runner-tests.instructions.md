---
applyTo: ".github/workflows/**,tools/database/runner/tests/**"
---

# Code rules for .github/workflows, tools/database/runner/tests

- Database project-discovery integration tests that invoke Gradle require a JDK and run separately from the Python unit suite. CI runs them on Linux after setting up Java and Gradle.
