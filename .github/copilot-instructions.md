# Repository code rules

Apply the same code rules to a checkout audit and a pull request review.

- In a checkout audit, report concrete violations anywhere in the requested scope. Cite the file and line.
- In a pull request review, use surrounding code as context, but report only violations introduced by the diff.

## Fixture readiness

- Check readiness at the protocol level. Verify that the service can run the required initialization or, if none is needed, serve the workload. An open port or zero exit status alone is not enough. Treat a protocol error as a failed probe even if the command exits successfully.

## Downloaded archives

- When repository code downloads a release or fixture archive directly, verify it against a pinned digest before extracting or installing it. Use the digest for the selected artifact, such as the host architecture's archive for OBI.
