---
applyTo: "docs/data/**,scenarios/**,tools/report/**"
---

# Code rules for docs/data, scenarios, tools/report

- Commit measured coverage as `data.json` beside each `conformance.yaml` and keep it in sync with the measured scenarios. The report builder derives `docs/data/conformance.json` from those records and the registry pins supplied by the domain packages; do not edit the aggregate by hand.
