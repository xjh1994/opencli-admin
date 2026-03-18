"""Claude (Anthropic) AI processor."""

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
class ClaudeProcessor(AbstractProcessor):
    """Process records using Anthropic Claude."""

    processor_type = "claude"

    async def process(
        self,
        records: list["CollectedRecord"],
        prompt_template: str,
        config: dict[str, Any],
    ) -> ProcessingResult:
        try:
            import anthropic
        except ImportError:
            return ProcessingResult(
                success=False, error="anthropic package not installed"
            )

        api_key = config.get("api_key") or __import__("os").environ.get("ANTHROPIC_API_KEY", "")
        model = config.get("model", "claude-haiku-4-5-20251001")
        max_tokens = config.get("max_tokens", 1024)

        client = anthropic.AsyncAnthropic(api_key=api_key)
        enrichments: list[dict[str, Any]] = []

        for record in records:
            prompt = _render(prompt_template, record.normalized_data)
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                # Try to parse JSON; fall back to raw text
                try:
                    enrichment = json.loads(text)
                except json.JSONDecodeError:
                    enrichment = {"analysis": text}
                enrichments.append(enrichment)
            except Exception as exc:
                enrichments.append({"error": str(exc)})

        return ProcessingResult(success=True, enrichments=enrichments)
