"""Local model processor via Ollama/vLLM compatible API."""

import json
import re
from typing import TYPE_CHECKING, Any

import httpx

from backend.processors.base import AbstractProcessor, ProcessingResult
from backend.processors.registry import register_processor

if TYPE_CHECKING:
    from backend.models.record import CollectedRecord

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, data: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), template)


@register_processor
class LocalProcessor(AbstractProcessor):
    """Process records using a locally hosted model (Ollama/vLLM)."""

    processor_type = "local"

    async def process(
        self,
        records: list["CollectedRecord"],
        prompt_template: str,
        config: dict[str, Any],
    ) -> ProcessingResult:
        base_url = config.get("base_url", "http://localhost:11434")
        model = config.get("model", "llama3")
        timeout = config.get("timeout", 120)
        # Support both Ollama (/api/generate) and OpenAI-compatible (/v1/chat/completions)
        api_style = config.get("api_style", "ollama")

        enrichments: list[dict[str, Any]] = []

        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            for record in records:
                prompt = _render(prompt_template, record.normalized_data)
                try:
                    if api_style == "ollama":
                        resp = await client.post(
                            "/api/generate",
                            json={"model": model, "prompt": prompt, "stream": False},
                        )
                        resp.raise_for_status()
                        text = resp.json().get("response", "")
                    else:
                        # OpenAI-compatible
                        resp = await client.post(
                            "/v1/chat/completions",
                            json={
                                "model": model,
                                "messages": [{"role": "user", "content": prompt}],
                            },
                        )
                        resp.raise_for_status()
                        text = resp.json()["choices"][0]["message"]["content"]

                    try:
                        enrichment = json.loads(text)
                    except json.JSONDecodeError:
                        enrichment = {"analysis": text}
                    enrichments.append(enrichment)
                except Exception as exc:
                    enrichments.append({"error": str(exc)})

        return ProcessingResult(success=True, enrichments=enrichments)
