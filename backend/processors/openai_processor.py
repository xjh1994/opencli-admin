"""OpenAI AI processor."""

import json
import re
from typing import TYPE_CHECKING, Any

from backend.processors.base import AbstractProcessor, ProcessingResult
from backend.processors.registry import register_processor

if TYPE_CHECKING:
    from backend.models.record import CollectedRecord

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, data: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), template)


@register_processor
class OpenAIProcessor(AbstractProcessor):
    """Process records using OpenAI models."""

    processor_type = "openai"

    async def process(
        self,
        records: list["CollectedRecord"],
        prompt_template: str,
        config: dict[str, Any],
    ) -> ProcessingResult:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ProcessingResult(success=False, error="openai package not installed")

        api_key = config.get("api_key") or __import__("os").environ.get("OPENAI_API_KEY", "")
        base_url: str | None = config.get("base_url") or None
        model = config.get("model", "gpt-4o-mini")
        max_tokens = config.get("max_tokens", 1024)
        # response_format=json_object is OpenAI-specific; skip for other providers
        use_json_mode = config.get("json_mode", base_url is None)

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        enrichments: list[dict[str, Any]] = []

        for record in records:
            prompt = _render(prompt_template, record.normalized_data)
            try:
                kwargs: dict[str, Any] = dict(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await client.chat.completions.create(**kwargs)
                text = response.choices[0].message.content or "{}"
                try:
                    enrichment = json.loads(text)
                except json.JSONDecodeError:
                    enrichment = {"analysis": text}
                enrichments.append(enrichment)
            except Exception as exc:
                enrichments.append({"error": str(exc)})

        return ProcessingResult(success=True, enrichments=enrichments)
