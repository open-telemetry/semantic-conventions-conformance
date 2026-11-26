---
applyTo: "scenarios/gen-ai/**"
---

# GenAI scenarios

- Each GenAI workload performs the exchange defined for its scenario class, using the client SDK's equivalents for the documented request settings and message roles it supports.

- Each GenAI scenario class has its own workload file named after the class, and every implemented class is listed in `scenarios/gen-ai/README.md`.

- GenAI workloads do not work around missing or incorrect mock responses. Every response field and behavior a workload depends on is served by `tools/gen-ai/mock-server`.

- `inference` and `streaming` requests include every sampling option that has a GenAI semantic convention attribute and that the client API accepts. Use the SDK's parameter names and omit options it cannot express.

- Each GenAI implementation measures only its own instrumentation. A Python implementation environment must not contain another auto-discoverable instrumenter, and a JavaScript implementation package must not declare another instrumenter even though it shares an npm workspace.

- GenAI configurations record telemetry without `expected_violations` or span, metric, or event expectations. A span `match` with `type` and no `expect` is allowed only when reduction cannot classify the span otherwise; document why the hint is needed and remove it once the span identifies itself.

- GenAI configurations map `${MOCK_SERVER_URL}` to the client SDK's native base-URL environment variable. The workload reads and passes an injected URL itself only when the SDK has no such setting.

- When a GenAI client SDK emits its own OpenTelemetry, disable that telemetry in environments measuring a separate instrumentation. For example, set `ANTHROPIC_OPEN_TELEMETRY: "false"` when measuring a separate Anthropic instrumentation. Keep the SDK's telemetry enabled in the `native` environment that measures it.

- Enable GenAI content capture for the entire implementation directory, never per scenario. Use `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` where the instrumentation reads it, or the implementation's own setting where one is needed. Because `data.json` combines coverage across the directory, mixed capture modes can hide that some scenarios ran with capture off.
