---
applyTo: "tools/gen-ai/mock-server/**"
---

# Code rules for tools/gen-ai/mock-server

- Mock provider responses are byte-identical for identical stateless requests. Stored OpenAI responses may depend on an earlier create, but replaying the same sequence from the same starting state produces the same bytes.

- Each non-streaming OpenAI `background` create returns a distinct response ID, even when the request body is identical.

- Polling a non-streaming OpenAI background response returns `in_progress` on the first `GET` for its ID and `completed` on subsequent `GET` requests for that ID.
