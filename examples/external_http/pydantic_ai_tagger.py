"""Pydantic-AI reference backend for external_http.

Demonstrates the contract using Pydantic AI's typed agent: one ``Agent``
with an ``output_type`` schema produces validated structured output in
a single LLM call. No tool loop, no multi-step investigation -- this
is the L1 ("simple tagger") reference. Pydantic AI's lib-shape makes
upgrading to L2/L3 (add tools) a 10-line change later.

Run:
    ANTHROPIC_API_KEY=sk-ant-... uv run python examples/external_http/pydantic_ai_tagger.py

Or against a local Ollama:
    AGENT_BACKEND=ollama AGENT_MODEL=qwen3:8b \
        uv run python examples/external_http/pydantic_ai_tagger.py

Requires (not in opencli-admin's deps, install separately):
    uv pip install pydantic-ai
"""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="external_http -- pydantic-ai tagger")


class Enrichment(BaseModel):
    tags: list[str] = Field(min_length=1, max_length=10)
    summary: str
    priority: int = Field(ge=1, le=5)
    sentiment: Literal["positive", "neutral", "negative", "mixed"] = "neutral"


_BACKEND = os.environ.get("AGENT_BACKEND", "anthropic")
_MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-4-5-20251001")
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _build_agent():
    from pydantic_ai import Agent

    if _BACKEND == "anthropic":
        model: Any = f"anthropic:{_MODEL}"
    elif _BACKEND == "openai":
        model = f"openai:{_MODEL}"
    elif _BACKEND == "ollama":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            base_url=f"{_OLLAMA_HOST.rstrip('/')}/v1",
            api_key="ollama",
        )
        model = OpenAIChatModel(_MODEL, provider=provider)
    else:
        raise ValueError(f"unknown AGENT_BACKEND: {_BACKEND}")

    return Agent(
        model,
        system_prompt=(
            "You are a content tagger. Read the user message and return the "
            "Enrichment schema: 3-8 lowercase keyword tags, one-paragraph "
            "summary in the input language, priority 1-5 (1=noise, 5=urgent), "
            "sentiment positive/neutral/negative/mixed."
        ),
        output_type=Enrichment,
    )


_AGENT = None


def _agent():
    global _AGENT
    if _AGENT is None:
        _AGENT = _build_agent()
    return _AGENT


class ProcessRequest(BaseModel):
    prompt: str
    record: dict[str, Any] | None = None
    agent_id: str | None = None
    trace_id: str | None = None


@app.post("/process")
async def process(req: ProcessRequest) -> dict[str, Any]:
    result = await _agent().run(req.prompt)
    out: dict[str, Any] = result.output.model_dump()
    usage = result.usage()
    out["_meta"] = {
        "model": _MODEL,
        "backend": _BACKEND,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "trace_id": req.trace_id,
    }
    return out


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8088, log_level="warning")
