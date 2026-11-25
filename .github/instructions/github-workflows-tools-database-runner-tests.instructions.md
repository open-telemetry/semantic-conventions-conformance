---
applyTo: ".github/workflows/**,tools/database/runner/tests/**"
---

# Code rules for .github/workflows, tools/database/runner/tests

- Database project-discovery tests that invoke real Gradle builds run separately from the default Python unit suite under `OTEL_CONFORMANCE_TEST_JAVA_DISCOVERY=1`. CI enables them in the Linux integration step after setting up Java and Gradle.
