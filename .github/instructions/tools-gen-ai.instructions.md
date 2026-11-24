---
applyTo: "tools/gen-ai/**"
---

# Code rules for tools/gen-ai

- For GenAI span classification, check `mcp.method.name` first. Otherwise, an explicit `gen_ai.operation.name` takes precedence over compatibility attributes, which may infer a type only when the operation is absent.
- Limit the GenAI live-check exclusions for configured Node SDK host and process detector attributes to resource findings. The same filter must not suppress findings on spans, metrics, or events.
