---
applyTo: "scenarios/gen-ai/**,tools/gen-ai/mock-server/**"
---

# Code rules for the GenAI mock server

- GenAI mock responses must be byte-for-byte deterministic for the same request. Stored OpenAI responses may depend on prior calls, but repeating the same call sequence must still produce the same bytes.
