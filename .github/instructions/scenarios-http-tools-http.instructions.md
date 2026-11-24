---
applyTo: "scenarios/http/**,tools/http/**"
---

# Code rules for scenarios/http, tools/http

- Use the shared HTTP exchange contract rather than restating the traffic per library or language. Client scenarios send contract requests through the measured client and verify response status and parsed JSON. Server scenarios are driven externally and express routing in the framework's native form.
- JavaScript browser and Node HTTP clients share response rendering and verification in a browser-safe module separate from the Node-only YAML loader. Compare parsed JSON, identify the request when parsing fails, and interpolate request bodies literally so patterns such as `$&` are not expanded.
