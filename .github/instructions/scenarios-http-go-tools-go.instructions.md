---
applyTo: "scenarios/http/go/**,tools/go/**"
---

# Code rules for scenarios/http/go, tools/go

- Go scenarios compile in `setup:` and execute the prepared binary during the measured `run:`, rather than compiling with `go run`.
