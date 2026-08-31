# HTTP conformance mock server

Answers the exchanges an HTTP conformance scenario sends, so a *client*
scenario has something to call. A server scenario is its own server and
doesn't need this.

```sh
pip install -e tools/http/test-client/python -e tools/http/mock-server
http-mock-server --port 8080
curl localhost:8080/health
```

The runner starts it for you: a `conformance.yaml` declares it under
`server:`, and the runner publishes its base URL as `${MOCK_SERVER_URL}`.

It answers the exchanges in
[`otel-http-test-client`](../test-client) rather than restating them — the same
traffic the external driver sends to a server scenario, so both sides of the
domain are measured consistently. It is stricter about one thing than a server
scenario is: nothing reads the answer a client scenario receives, so a request
whose declared body does not arrive gets a 400 rather than an echo of nothing.
Standard library only, and never instrumented: it runs as a separate process
and nothing it emits should reach the report.
