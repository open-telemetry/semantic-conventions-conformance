# Repository code rules

Apply the same code rules to a checkout audit and a pull request review.

- In a checkout audit, report concrete violations anywhere in the requested scope. Cite the file and line.
- In a pull request review, use surrounding code as context, but report only violations introduced by the diff.

## Fixtures

- Check readiness at the protocol level. Verify that the service can run the required initialization or, if none is needed, serve the workload. An open port or zero exit status alone is not enough. Treat a protocol error as a failed probe even if the command exits successfully.
- If a workload needs behavior a mock does not provide, change the mock or its shared contract instead of working around it in the scenario. Cover changed mock behavior with tests.

## Downloaded archives

- When repository code or a workflow downloads a release or fixture archive directly, verify it against a pinned digest before extracting or installing it. Use the digest for the selected artifact, such as the host architecture's archive for OBI.
- This does not apply to a source archive that GitHub generates for a git ref, such as the semantic-convention registry the runner fetches. GitHub does not guarantee those bytes stay the same, so a pinned digest can break without the content changing.

## Scenario contracts

- In a list-based `scenario_contract`, keep each workload `action` alongside its telemetry `expect` mapping. Adapters use the runner's selected action or index rather than defining the workload again.
- When explicitly checking an attribute value or presence required by the semantic conventions, use `expect.semantic_conventions` so deviations are recorded as findings. Do not change the requirement to match what the client currently emits.

## Scenario instrumentation

- Keep instrumentation setup out of shared workload code. Configure only the instrumentation under test and any companions it needs, in the launcher or implementation environment.
- When measuring out-of-process instrumentation such as OBI, run the shared workload without configuring an in-process SDK or attaching another agent.

## Scenario tooling

- When `conformance.yaml` declares `runner:`, use that wrapper to supply the registry and policies. Neither the runner nor its callers, including CI, should infer the wrapper from the scenario path.
- When discovering scenario packages or subprojects, skip dependency trees and generated output even if they contain files that match the discovery pattern.
