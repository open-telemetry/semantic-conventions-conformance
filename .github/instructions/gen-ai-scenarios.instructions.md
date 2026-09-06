---
applyTo: "scenarios/gen-ai/**,tools/gen-ai/mock-server/**"
---

# Reviewing GenAI conformance scenarios

The contract these have to obey is in
[`scenarios/gen-ai/README.md`](../../scenarios/gen-ai/README.md). The rules for
changing the tree are in
[`scenarios/gen-ai/AGENTS.md`](../../scenarios/gen-ai/AGENTS.md). Review
against those, and check:

- **Comparability.** Does the scenario make the exchange its class defines, in
  the same shape as the same class under the other libraries? A scenario that
  sets fewer request options than its siblings makes its `data.json` look like
  an instrumentation gap when it is a scenario gap. Where an option is absent
  because the API has no such parameter, say so.
- **One class per file**, named after the class. Two classes merged into one
  program, or a class not listed in the README, needs the README changed
  first.
- **No OpenTelemetry import and no instrumentation named** in a scenario
  program, and no configuration read beyond the client library's own
  environment variables. Telemetry needing programmatic configuration gets an
  entry program beside `conformance.yaml`, importing the shared scenario.
- **One instrumentation per implementation environment.** A second one in
  `pyproject.toml` puts another library's spans in the results.
- **`data.json` regenerated and committed**, matching the scenarios as
  changed. CI fails on a diff.
- **Mock server changes** carry a test and stay deterministic: same request,
  same bytes. A scenario working around a missing mock response is the wrong
  fix.
- **No expectations declared.** No `expected_violations`, and no `spans`,
  `metrics` or `events` blocks. Scenarios here measure; a finding is a result
  this repo exists to record, so anything that quiets one is a defect.
