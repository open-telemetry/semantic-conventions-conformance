---
applyTo: "tools/database/**"
---

# Code rules for tools/database

- Use the database backend registry as the source of truth for backend factories, database system names, and client span types. Resolve each factory from its registration and classify only client spans for registered systems.
- A database session owns its disposable backend and closes it even on failure. Readiness probes must fail when the server responds but cannot serve the workload; use the client CLI's error-exit option if it otherwise reports success. Skip initialization for backends that require no fixture.
- Prepared SQL actions use positional `${1}`, `${2}`, and subsequent markers, each appearing once in ascending order with one typed parameter per marker. Reject malformed, missing, repeated, or out-of-order markers before sending SQL to the client.
- If a shared stored-procedure contract asserts exact query text, the action must carry the call SQL explicitly. Adapters must not construct their own call text from the procedure name.
