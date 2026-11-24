---
applyTo: "scenarios/gen-ai/**"
---

# Code rules for scenarios/gen-ai

Use the [scenario contract](../../scenarios/gen-ai/README.md#the-scenario-contract) and the [implementation rules](../../scenarios/gen-ai/AGENTS.md).

- Make each implementation of a class exercise the same exchange. For `inference` and `streaming`, send every sampling option the conventions cover that the client API accepts. Document any omitted option the API cannot express.
- Keep one file per class, named after the class. Define new classes in the scenario contract.
- Keep shared scenario programs free of OpenTelemetry imports and instrumentation names. Use the client library's own configuration where available, and put any programmatic instrumentation setup in an entry point beside `conformance.yaml`. Each implementation environment installs only the instrumentation it measures.
- GenAI scenarios must not declare `expected_violations` or span, metric, or event expectations. A span the reduction cannot place may use a `match` with `type` but no `expect`, leaving all findings recorded.
