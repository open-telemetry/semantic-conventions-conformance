---
applyTo: "tools/gen-ai/mock-server/**"
---

# Code rules for tools/gen-ai/mock-server

- Mock provider responses are byte-identical for identical stateless requests. Stored OpenAI responses may depend on an earlier create, but replaying the same sequence from the same starting state produces the same bytes.

- Each OpenAI Responses API create that returns `queued` gets a distinct response ID, even when the request body is identical.

- If an OpenAI Responses API create returns `queued`, the first `GET` for that response ID returns `in_progress` and subsequent `GET` requests return `completed`.
