---
applyTo: "scenarios/database/contracts/**,tools/database/sql-test-client/contracts/**"
---

# Code rules for scenarios/database/contracts, tools/database/sql-test-client/contracts

- A semantic expectation for `db.namespace` uses the meaning defined by the pinned backend convention, not a driver-specific identifier. Oracle uses `DB_UNIQUE_NAME`, not the PDB or service name, and PostgreSQL includes the schema in `{database}|{schema}` when the schema is available.

- Database attribute requirements meant to surface semantic-convention gaps belong under `expect.semantic_conventions`, not as hard `expect.attributes` assertions. This lets the contract record a stable-convention gap even if it separately checks the legacy telemetry the client actually emits.
