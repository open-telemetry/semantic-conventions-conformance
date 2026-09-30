# .NET HTTP test client

The .NET decoder for runner-injected HTTP actions, enough for a scenario to
answer a concrete request or send one selected request.

`HttpContract` decodes `OTEL_CONFORMANCE_SCENARIO_ACTION` and
`OTEL_CONFORMANCE_SCENARIO_ACTIONS`. `HttpServerWorkload.Respond` looks up the answer
for any .NET framework, and `HttpClientWorkload.DriveAsync` sends one
runner-selected request through whatever the scenario hands it. Both halves are
exercised against each other by this project's unit tests, so a change to either
is caught here rather than by a scenario failing a run.

The package has no YAML parser or embedded contract. The runner supplies the
selected client action and the complete server action table as JSON.

A client launch handles exactly one `OTEL_CONFORMANCE_SCENARIO_ACTION` and then
exits. A server launch decodes `OTEL_CONFORMANCE_SCENARIO_ACTIONS` once and stays
alive while the external driver sends those actions sequentially.

`HttpClientWorkload.Sender` returns a `Task`, because the .NET HTTP libraries a
scenario measures are asynchronous and forcing a synchronous shape onto them
would measure a blocking call the library was never meant to make.
