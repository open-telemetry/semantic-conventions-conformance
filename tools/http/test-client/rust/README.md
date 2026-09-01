# Rust HTTP conformance test client

This crate is the Rust view of
[`../contract.json`](../contract.json). `include_str!` embeds that one existing
file at compile time, so Rust never vendors or rewrites the contract.

`exchanges()` and `requests()` expose the traffic, `respond()` supplies the
server half, and `drive()` sends the client half through a caller-supplied
asynchronous sender. The sender belongs to the workload because it must use the
HTTP library under test. `verify()` compares statuses exactly and bodies as
JSON values. `scenario_port()` reads the port selected by `otel-http-drive`.

The unit tests drive the client loop against `respond()`, which checks both
halves against the same embedded data.
