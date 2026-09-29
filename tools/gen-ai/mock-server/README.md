# GenAI mock LLM server

A Flask app that answers the wire protocols of the GenAI providers with fixed
responses, so a conformance scenario exercises a real client library without a
real provider and without cassette replay. Same request in, same bytes out —
that determinism is what makes a scenario's expectations checkable.

```sh
genai-mock-server --port 8080          # or: python -m genai_mock_server
curl localhost:8080/health
```

The conformance runner starts it for you: a directory declares it under
`server:`, and the runner publishes its base URL to the scenario as
`${MOCK_SERVER_URL}`.

## What it answers

| Blueprint | Endpoints |
| --- | --- |
| `anthropic` | `/v1/messages`, including tool use, streaming and compaction |
| `anthropic_agents`, `mistral_agents` | hosted-agent creation |
| `assistants` | OpenAI Assistants, threads and runs |
| `bedrock` | `converse`, `converse-stream`, `invoke` |
| `bedrock_agent`, `bedrock_agentcore` | agent invocation and the memory APIs |
| `cohere` | `/v1` and `/v2` chat and embed |
| `google_genai` | Gemini `generateContent` / streaming, and the Vertex `projects/…` paths |
| `mistral` | chat completions, FIM and embeddings, under `/mistral/v1/…` |
| `ollama` | `/api/chat`, including tool use and NDJSON streaming, and `/api/embed` |
| `openai` | chat completions, embeddings and the Responses API, under `/v1/…`, the Azure `/openai/deployments/<deployment>/…` paths, and bare paths |

Behaviour follows the request rather than configuration: `stream: true` gets an
SSE response, offered `tools` get a tool call, and the requested model is
echoed back. Ids and token counts are fixed.

## Adding a response

A scenario that needs a field the server doesn't serve is a change here, not a
workaround in the scenario. Add it to the provider's blueprint, cover it in
`tests/`, and keep the response deterministic.

> This server was moved here from
> `semantic-conventions-genai/reference/src/semconv_genai/mock_server`, which
> still carries a copy while its own scenarios are migrated. Changes belong
> here; the copy there is going away.
