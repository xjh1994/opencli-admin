"""Claude (Anthropic) AI processor."""

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from backend.processors.base import AbstractProcessor, ProcessingResult
from backend.processors.registry import register_processor

if TYPE_CHECKING:
    from backend.models.record import CollectedRecord

logger = logging.getLogger(__name__)

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

        logger.info("claude processor | model=%s max_tokens=%d records=%d",
                    model, max_tokens, len(records))

        client = anthropic.AsyncAnthropic(api_key=api_key)
        enrichments: list[dict[str, Any]] = []

        for i, record in enumerate(records):
            prompt = _render(prompt_template, record.normalized_data)
            logger.debug("claude req [%d/%d] | prompt_preview=%s",
                         i + 1, len(records), prompt[:200])
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                usage = response.usage
                logger.info("claude resp [%d/%d] | input_tokens=%d output_tokens=%d preview=%s",
                            i + 1, len(records),
                            usage.input_tokens, usage.output_tokens,
                            text[:200])
                try:
                    enrichment = json.loads(text)
                except json.JSONDecodeError:
                    enrichment = {"analysis": text}
                enrichments.append(enrichment)
            except Exception as exc:
                logger.error("claude error [%d/%d] | %s", i + 1, len(records), exc)
                enrichments.append({"error": str(exc)})

        logger.info("claude processor done | success=%d errors=%d",
                    sum(1 for e in enrichments if "error" not in e),
                    sum(1 for e in enrichments if "error" in e))
        return ProcessingResult(success=True, enrichments=enrichments)
