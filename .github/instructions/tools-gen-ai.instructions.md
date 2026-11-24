---
applyTo: "tools/gen-ai/**"
---

# Code rules for tools/gen-ai

- GenAI mock responses must be byte-for-byte deterministic for the same request. Stored OpenAI responses may depend on prior calls, but repeating the same call sequence must still produce the same bytes.
