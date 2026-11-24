---
applyTo: "scenarios/gen-ai/**,tools/gen-ai/mock-server/**"
---

# Code rules for the GenAI mock server

- Add missing response fields or behavior to the provider mock, not to the scenario. Cover changed mock behavior with tests.
- GenAI mock responses must be byte-for-byte deterministic for the same request. Stored OpenAI responses may depend on prior calls, but repeating the same call sequence must still produce the same bytes.
