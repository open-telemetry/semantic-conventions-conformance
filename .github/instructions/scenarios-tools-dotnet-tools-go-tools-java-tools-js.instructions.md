---
applyTo: "scenarios/**,tools/dotnet/**,tools/go/**,tools/java/**,tools/js/**"
---

# Code rules for scenarios, tools/dotnet, tools/go, tools/java, tools/js

- For Java, JavaScript, Go, and .NET, keep the scenario build root and instrumentation dependency pins under `scenarios/<domain>/<language>/`. Consume shared tooling from the checkout under `tools/` rather than duplicating it or requiring a published release. Shared tooling may own separate dependency pins.
