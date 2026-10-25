# GenAI mock LLM server

A Flask server that returns fixed responses in each provider's API format.
Conformance scenarios use real client libraries against it, without provider
credentials or recorded cassettes.

```sh
genai-mock-server --port 8080          # or: python -m genai_mock_server
curl localhost:8080/health
```

Declare the server under `server:` in `conformance.yaml`. The runner starts it
and supplies its URL as `${MOCK_SERVER_URL}`.

## Supported APIs

| Blueprint | Endpoints |
| --- | --- |
| `anthropic` | `/v1/messages`, including client tools, non-streaming web search, streaming text and compaction |
| `anthropic_agents`, `mistral_agents` | hosted-agent creation |
| `assistants` | OpenAI Assistants, threads and runs |
| `bedrock` | `converse`, `converse-stream`, `invoke` |
| `bedrock_agent`, `bedrock_agentcore` | agent invocation, knowledge-base retrieval/generation (including streaming), and the memory APIs |
| `cohere` | `/v1` and `/v2` chat and embed |
| `google_genai` | Gemini and Vertex content generation, code execution, and interaction creation/retrieval with Google Search |
| `mistral` | chat completions, FIM and embeddings, under `/mistral/v1/…` |
| `ollama` | `/api/chat`, including tool use and NDJSON streaming, and `/api/embed` |
| `openai` | chat completions, embeddings and the Responses API (including non-streaming web search), under `/v1/…`, the Azure `/openai/deployments/<deployment>/…` paths, and bare paths |

Responses depend on the request's model, tools, and streaming options. Most
endpoints return fixed IDs and token counts; resource-creation endpoints may
assign new IDs. Streaming formats follow the provider's API.

## Google interactions and hosted tools

`GET /v1beta/interactions/{id}` returns a completed interaction with the requested
ID, model output, and token usage. No create request is needed, so a fetch
scenario emits only retrieval telemetry.

Non-streaming Gemini and Vertex `generateContent` requests with `codeExecution`
return fixed code and execution results. With `googleSearch` they return
grounding metadata and a text answer, plus `toolCall`/`toolResponse` parts when
`toolConfig.includeServerSideToolInvocations` is set. Sent next to
`functionDeclarations`, the answer is a function call instead of text.
Interaction creation requests with `google_search` return a search call, its
result, and model output. The server does not execute code or search the web.

For OpenAI chat completions, streamed or not, a request whose last user message contains
`[MOCK_EMPTY_COMPLETION]` gets an empty completion whose usage reports `completion_tokens: 0`, and one
whose last user message contains `[MOCK_BAD_REQUEST]` gets a 400 `invalid_request_error` with no usage.
Markers in earlier turns or in system, assistant, or tool messages are ignored.
They exist so a scenario can exercise the zero-output and failed-call paths of
token usage recording.

## Adding a response

Add missing fields or endpoints to the provider module and cover them in
`tests/`. Keep responses deterministic so scenarios can assert their values.

This server was moved from
`semantic-conventions-genai/reference/src/semconv_genai/mock_server`. That copy
remains during migration; add changes here.
