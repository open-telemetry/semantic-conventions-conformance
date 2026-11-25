---
applyTo: "tools/gen-ai/mock-server/**"
---

# Code rules for tools/gen-ai/mock-server

- The GenAI mock returns identical bytes for identical requests, except that stored OpenAI responses reflect the earlier create and non-streaming background creates allocate a fresh ID whose first poll reports `in_progress`.
