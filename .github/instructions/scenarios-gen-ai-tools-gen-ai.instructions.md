---
applyTo: "scenarios/gen-ai/**,tools/gen-ai/**"
---

# Code rules for scenarios/gen-ai, tools/gen-ai

- If a GenAI exchange needs a response field, implement and test it in the provider mock rather than working around it in the workload. Identical requests produce identical response bytes except where the protocol depends on prior calls, such as stored responses and background polling; those sequences must still be reproducible across runs.
