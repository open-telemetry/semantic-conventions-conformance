---
applyTo: "scenarios/database/**,tools/database/**"
---

# Code rules for scenarios/database, tools/database

- Keep each backend's SQL action alongside its generic telemetry expectations in the shared contract. Pass the selected action to the language helper as JSON and have the helper translate it into client API calls.
- When the applicable semantic convention specifies a value or requires an attribute, keep that requirement distinct from what the client currently emits and record deviations as findings.
