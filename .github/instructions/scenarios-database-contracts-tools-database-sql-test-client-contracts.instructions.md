---
applyTo: "scenarios/database/contracts/**,tools/database/sql-test-client/contracts/**"
---

# Code rules for scenarios/database/contracts, tools/database/sql-test-client/contracts

- Database telemetry expectations follow the backend's semantic conventions for the signal, not one driver's output. Use `expect.semantic_conventions`, not ordinary `expect.attributes`, for attribute requirements whose mismatches should be recorded as conformance findings. Keep known mismatches visible; do not require an attribute the convention does not define for that signal.
