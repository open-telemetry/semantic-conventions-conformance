---
applyTo: "scenarios/browser/**,scenarios/http/**,tools/js/**"
---

# Code rules for scenarios/browser, scenarios/http, tools/js

- The shared browser runner serves the page, OTLP relay, and any proxied HTTP fixture from one origin. Keep export routes separate from workload routes, preserve the contract path and query through the fixture proxy, and relay HTTP/protobuf to the runner-injected endpoint rather than implementing a separate gRPC bridge.
- Report browser page errors and surface initialization errors as load failures, not generic result timeouts. Once the workload is exposed, page errors are diagnostic because a workload may deliberately raise them to measure exception telemetry.
- Bound waits for asynchronous browser telemetry and report expected and observed counts on timeout. A launcher deadline must also cover a page that never publishes a result.
