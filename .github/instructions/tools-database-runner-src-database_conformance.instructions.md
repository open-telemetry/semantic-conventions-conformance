---
applyTo: "tools/database/runner/src/database_conformance/**"
---

# Code rules for tools/database/runner/src/database_conformance

- A readiness probe succeeds only when the backend can perform the operations needed for fixture initialization, not merely when it accepts connections. A server error reply does not count as success even if the probe client exits zero.
