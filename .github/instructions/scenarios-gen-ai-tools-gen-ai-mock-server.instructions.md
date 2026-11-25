---
applyTo: "scenarios/gen-ai/**,tools/gen-ai/mock-server/**"
---

# Code rules for scenarios/gen-ai, tools/gen-ai/mock-server

- Provider mocks supply response fields that GenAI workloads need, with tests for the relevant response branches. Workloads do not fabricate missing provider fields.
