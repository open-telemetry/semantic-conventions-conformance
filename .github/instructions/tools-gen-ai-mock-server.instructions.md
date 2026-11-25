---
applyTo: "tools/gen-ai/mock-server/**"
---

# Code rules for tools/gen-ai/mock-server

- Identical mock requests return identical response bytes unless the response depends on earlier calls, such as stored-response retrieval or background polling. Stateful exchanges still return identical bytes across runs for the same ordered calls.
