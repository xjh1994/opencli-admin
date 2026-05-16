"""Reference HTTP agent server for the external_http processor.

Run:
    uv run python examples/external_http/stub.py

It listens on http://127.0.0.1:8088/process and returns a synthetic
enrichment for each record, demonstrating the contract that opencli-admin's
ExternalProcessor expects from any external agent runtime.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="external_http stub agent")


class ProcessRequest(BaseModel):
    prompt: str
    record: dict[str, Any] | None = None
    agent_id: str | None = None
    trace_id: str | None = None


@app.post("/process")
async def process(req: ProcessRequest) -> dict[str, Any]:
    """Echo a synthetic enrichment.

    Any JSON dict shape is acceptable; opencli-admin stores it verbatim.
    A real agent (Pydantic AI, dify flow, custom LLM caller) would render
    a prompt against its model and return tags/summary here.
    """
    title = (req.record or {}).get("title", "(no title)")
    return {
        "tags": ["smoke-test", f"agent:{req.agent_id or 'default'}"],
        "summary": f"Stub processed: {title[:80]}",
        "prompt_chars": len(req.prompt),
        "echo_agent_id": req.agent_id,
        "_meta": {
            "model": "stub",
            "input_tokens": len(req.prompt),
            "output_tokens": 0,
            "trace_id": req.trace_id,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8088, log_level="warning")
