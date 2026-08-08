# HTTP conformance mock server

Answers the routes an HTTP conformance scenario expects, so a *client*
scenario has something to call. A server scenario is its own server and
doesn't need this.

```sh
pip install -e tools/http/mock-server
http-mock-server --port 8080
curl localhost:8080/health
```

The runner starts it for you: a `conformance.yaml` declares it under
`server:`, and the runner publishes its base URL as `${MOCK_SERVER_URL}`.

The routes are the contract in
[`otel-http-test-client`](../test-client) — the same one a server scenario's
app implements, so both sides of the domain are measured against the same
traffic. Standard library only, and never instrumented: it runs as a separate
process and nothing it emits should reach the report.
