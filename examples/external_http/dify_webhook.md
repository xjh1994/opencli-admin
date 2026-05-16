# Dify as an external_http backend

[Dify](https://github.com/langgenius/dify) is an open-source LLM application builder with a
visual workflow editor, built-in model routing, and HTTP-trigger support. The `external_http`
processor in opencli-admin is a plain HTTP socket: it POSTs a JSON payload to any URL and
stores whatever JSON dict comes back. Combining them gives you a no-code agent backend --
build the enrichment logic in Dify's UI, point opencli-admin at the trigger URL, and skip
writing Python altogether.

## Inbound contract

When opencli-admin fires a record, the Dify HTTP-Trigger node receives a POST with
`Content-Type: application/json` and a body shaped like this:

```json
{
  "prompt": "Classify this event: user logged in from 192.0.2.44 at 03:12 UTC",
  "record": {
    "event_type": "auth.login",
    "ip": "192.0.2.44",
    "timestamp": "2026-05-17T03:12:00Z"
  },
  "agent_id": "dify-triage",
  "trace_id": "a3f9c2e10b84"
}
```

`record` is present only when `send_record: true` (the default). `agent_id` is present only
when set in the agent config. `trace_id` is a 12-character hex string unique to this record
invocation.

## Workflow shape

A minimal Dify workflow for this integration has four nodes:

| Node | Purpose |
|---|---|
| **HTTP Start (Trigger)** | Receives the POST; exposes `body.prompt`, `body.record`, `body.trace_id` as variables |
| **LLM** | Receives `prompt` as the user message; returns a structured completion |
| **Code** | Parses the LLM output; builds the response dict including `_meta` |
| **HTTP Response** | Returns `Content-Type: application/json` with the Code node output |

The Code node is where you map LLM output fields to the expected response keys and echo
`body.trace_id` into `_meta`. Keep the workflow synchronous -- opencli-admin waits for the
HTTP response.

## Response shape

The HTTP Response node must return a JSON object. opencli-admin stores it verbatim. All
top-level keys are optional; store whatever your workflow produces. A full example:

```json
{
  "tags": ["auth", "anomalous-hour"],
  "summary": "Login from unusual hour; IP not previously seen.",
  "priority": 3,
  "_meta": {
    "model": "gpt-4o",
    "input_tokens": 312,
    "output_tokens": 89,
    "trace_id": "a3f9c2e10b84"
  }
}
```

Echo the inbound `trace_id` into `_meta.trace_id` in the Code node so logs can be correlated.

If you want opencli-admin to validate the shape before storing it, add a `response_schema`
JSON Schema block to the agent config (see below). Responses that fail validation are logged
and dropped.

## Auth

Dify HTTP-Trigger nodes issue a secret token on creation. opencli-admin sends it on every
request as a bearer token:

```
Authorization: Bearer <your-dify-trigger-secret>
```

Set the same secret in the `auth_header` field of the agent config. opencli-admin adds the
header verbatim; no prefix is prepended.

## opencli-admin config

```yaml
ai_agents:
  - name: dify-triage
    type: external_http
    endpoint: https://dify.example.com/v1/workflows/run/abcdef1234567890
    auth_header: "Bearer dify_trigger_secret_goes_here"
    send_record: true
    agent_id: dify-triage
    # response_schema:
    #   type: object
    #   properties:
    #     tags:     { type: array, items: { type: string } }
    #     summary:  { type: string }
    #     priority: { type: integer, minimum: 1, maximum: 5 }
    #   required: [tags, summary, priority]
```

Replace `endpoint` with the HTTP-Trigger URL shown in the Dify workflow editor. The
`response_schema` block is optional; uncomment and adjust it if you want strict validation.

## Caveats

- **Latency.** Dify adds cold-start overhead the first time a workflow is triggered after
  idle. Set a generous HTTP timeout (30 s or more) in the opencli-admin processor config to
  avoid spurious failures.
- **No retries.** `external_http` does not retry on non-2xx responses. If the Dify workflow
  can fail (model timeout, rate limit), add error handling inside the workflow and always
  return a 2xx with a fallback JSON body.
- **Token counters.** Dify's usage dashboard counts tokens per workflow run. The `_meta`
  token totals logged by opencli-admin come from whatever the Code node writes -- they are
  independent of Dify's internal counters. Do not expect the two to match for batch runs.
