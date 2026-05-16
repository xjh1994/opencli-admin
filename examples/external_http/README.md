# external_http processor

The `external_http` processor POSTs each record to an HTTP endpoint and
stores the JSON response as the record's enrichment. The endpoint can be a
FastAPI script, an Anthropic/OpenAI wrapper, a dify workflow, langflow,
n8n, or an agent runtime that uses MCP tools behind its HTTP surface.

The contract is plain HTTP + JSON. opencli-admin renders the prompt,
sends one record, receives one JSON object, optionally validates it, and
stores the resulting enrichment.

## Files

- `stub.py` -- minimal echo agent (FastAPI, no LLM).
- `smoke.py` -- subprocess driver running `ExternalProcessor` against `stub.py`.
- `anthropic_tagger.py` -- production-shaped reference using Anthropic SDK directly.
- `pydantic_ai_tagger.py` -- alternative using Pydantic AI lib (Anthropic/OpenAI/Ollama).
- `mcp_proxy.md` -- how MCP composes with this contract.
- `dify_webhook.md` -- pointing an existing dify workflow at this contract.

## Request Contract

The processor sends one POST per record.

```json
{
  "prompt": "<rendered prompt>",
  "record": { "...": "..." },
  "agent_id": "<id>",
  "trace_id": "<12-char hex>"
}
```

- `prompt` is the resolved `prompt_template`.
- `record` is the record's normalized data. It is omitted when
  `config.send_record` is `false`.
- `agent_id` is copied from `config.agent_id`. It is omitted when unset.
- `trace_id` is always generated per record as a 12-character hex value.

## Response Contract

Backends return a JSON object.

```text
{
  "tags": ["..."],
  "summary": "...",
  "priority": 1-5,
  "_meta": { "model": "...", "input_tokens": N, "output_tokens": N }
}
```

- `tags` is an array of strings.
- `summary` is a string.
- `priority` is an integer from 1 to 5.
- `_meta` is optional backend telemetry.

The processor stores the response object as the enrichment. A non-dict
JSON value is wrapped as `{"analysis": <value>}`. Non-2xx responses,
network failures, and non-JSON bodies become error enrichments for that
record without aborting the batch.

## response_schema

`config.response_schema` is an optional JSON Schema. When present, the
processor validates each response before storing it.

This is backward compatible. Agents without `response_schema` keep the
previous behavior. Agents with `response_schema` reject only responses
that do not match the configured schema.

On mismatch, the stored enrichment is:

```json
{
  "error": "schema_violation",
  "details": "...",
  "trace_id": "<12-char hex>",
  "raw_response": { "...": "..." }
}
```

`details` contains the validation failure. `raw_response` is the backend
payload that failed validation.

## _meta Passthrough

Backends may include `_meta` in the response:

```json
{
  "_meta": {
    "model": "claude-sonnet-4-5",
    "input_tokens": 812,
    "output_tokens": 96,
    "cost": 0.0042
  }
}
```

The processor does not remove `_meta`; it stays in the stored enrichment.
When `_meta` is present, the processor logs per-record telemetry at INFO.
It also aggregates token totals for the batch and logs:

```text
external_http batch totals | input_tokens=N output_tokens=N
```

Only numeric `input_tokens` and `output_tokens` contribute to the batch
totals. `model` and `cost` remain per-record metadata.

## trace_id

Every request includes a new per-record `trace_id`:

```json
{
  "trace_id": "a3f09c12be77"
}
```

The value is 12 hex characters. It joins stored enrichments, processor
logs, and backend logs. Backends should log it for debugging but do not
need to return it on successful responses.

Error enrichments include `trace_id`, including schema violations.

## Agent Config

In an opencli-admin AI Agent, set:

```yaml
processor_type: external_http
config:
  endpoint: http://agent:8088/process
  timeout: 60
  auth_header: "Bearer "
  agent_id: tagger-news
  response_schema:
    type: object
    required: [tags, summary]
    properties:
      tags:    { type: array, items: { type: string } }
      summary: { type: string }
      priority: { type: integer, minimum: 1, maximum: 5 }
prompt_template: |
  Tag: {{title}}

  {{content}}
```

Additional supported config:

- `headers` adds static HTTP headers.
- `send_record` controls whether `record` is sent. Default is `true`.

## Run the smoke

```bash
uv run python examples/external_http/smoke.py
```

`smoke.py` starts `stub.py` automatically, sends sample records through
`ExternalProcessor`, and asserts the round trip.

`stub.py` does not call an LLM and does not need API keys.
`anthropic_tagger.py` and `pydantic_ai_tagger.py` are reference backends
for real model calls and need real API keys for the selected provider.

## MCP

The `external_http` processor does not speak MCP. It composes with MCP by
placing MCP behind the HTTP backend: opencli-admin sends HTTP to the
backend, and the backend calls MCP servers as tools. See `mcp_proxy.md`
for the integration shape.
