---
applyTo: "tools/gen-ai/mock-server/**"
---

# Code rules for tools/gen-ai/mock-server

- Mock provider responses are byte-identical for identical stateless requests. Stored OpenAI responses may depend on an earlier create, but replaying the same sequence from the same state produces the same bytes; a non-streaming `background` create gets its own ID, and only that ID's first `GET` reports `in_progress`.
