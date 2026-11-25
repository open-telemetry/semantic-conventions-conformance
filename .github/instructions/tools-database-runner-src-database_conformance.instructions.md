---
applyTo: "tools/database/runner/src/database_conformance/**"
---

# Code rules for tools/database/runner/src/database_conformance

- A backend readiness probe succeeds only when the backend can perform the operation the session needs next; an open connection or a client exit status that masks a server error does not establish readiness.
