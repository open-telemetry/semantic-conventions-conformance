---
applyTo: "scenarios/database/contracts/**,tools/database/sql-test-client/contracts/**"
---

# Code rules for scenarios/database/contracts, tools/database/sql-test-client/contracts

- Shared database telemetry contracts follow the pinned conventions for the backend and signal: they do not assert a known driver divergence as the correct value or require an attribute the model excludes.
