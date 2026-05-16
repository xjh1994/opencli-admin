"""Anthropic-native reference backend for external_http.

Demonstrates the contract using Anthropic's tool-use + structured output
features directly, with no agent-framework layer. Production-shaped: one
LLM call per record, ``_meta`` accounting reported to the processor.

Run:
    ANTHROPIC_API_KEY=sk-ant-... uv run python examples/external_http/anthropic_tagger.py

Then point an opencli-admin AI Agent at ``http://127.0.0.1:8088/process``
with ``processor_type: external_http``.

Contract notes:
- Reports ``_meta.input_tokens`` / ``output_tokens`` / ``model`` so the
  processor can aggregate per-batch usage in opencli-admin logs.
- Returns a JSON shape that satisfies the example ``response_schema``
  documented in README.md (tags, summary, priority, sentiment).
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

app = FastAPI(title="external_http -- anthropic tagger")
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise HTTPException(500, "ANTHROPIC_API_KEY not set")
        _client = anthropic.AsyncAnthropic(api_key=key)
    return _client


class ProcessRequest(BaseModel):
    prompt: str
    record: dict[str, Any] | None = None
    agent_id: str | None = None
    trace_id: str | None = None


_SYSTEM = (
    "You are a content tagger. Read the user message and respond with ONLY "
    "a JSON object. Fields: tags (list of 3-8 lowercase keyword strings), "
    "summary (one paragraph in the input language), priority (integer 1-5 "
    "where 1=noise and 5=urgent), sentiment (one of positive/neutral/"
    "negative/mixed). Do not wrap the JSON in markdown."
)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Anthropic occasionally fences JSON in markdown despite instruction.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return json.loads(text)


@app.post("/process")
async def process(req: ProcessRequest) -> dict[str, Any]:
    client = _get_client()

    msg = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": req.prompt}],
    )

    text_blocks = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    try:
        enrichment = _extract_json("\n".join(text_blocks))
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(502, f"model returned non-JSON: {e}") from e

    enrichment["_meta"] = {
        "model": msg.model,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
        "trace_id": req.trace_id,
        "stop_reason": msg.stop_reason,
    }
    return enrichment


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8088, log_level="warning")
