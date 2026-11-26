---
applyTo: ".github/workflows/**,tools/database/runner/tests/**"
---

# Java project-discovery tests

- Database project-discovery tests that invoke real Gradle builds are skipped unless `OTEL_CONFORMANCE_TEST_JAVA_DISCOVERY=1`.

- CI runs the Java project-discovery tests in a dedicated Linux step after setting up Java and Gradle, with `OTEL_CONFORMANCE_TEST_JAVA_DISCOVERY=1`.
