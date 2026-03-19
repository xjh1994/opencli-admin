"""OpenAI AI processor."""

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
        use_json_mode = config.get("json_mode", base_url is None)

        logger.info("openai processor | model=%s base_url=%s max_tokens=%d records=%d",
                    model, base_url or "(default)", max_tokens, len(records))

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        enrichments: list[dict[str, Any]] = []

        for i, record in enumerate(records):
            prompt = _render(prompt_template, record.normalized_data)
            logger.debug("openai req [%d/%d] | prompt_preview=%s",
                         i + 1, len(records), prompt[:200])
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
                usage = response.usage
                logger.info("openai resp [%d/%d] | prompt_tokens=%d completion_tokens=%d preview=%s",
                            i + 1, len(records),
                            usage.prompt_tokens if usage else -1,
                            usage.completion_tokens if usage else -1,
                            text[:200])
                try:
                    enrichment = json.loads(text)
                except json.JSONDecodeError:
                    enrichment = {"analysis": text}
                enrichments.append(enrichment)
            except Exception as exc:
                logger.error("openai error [%d/%d] | %s", i + 1, len(records), exc)
                enrichments.append({"error": str(exc)})

        logger.info("openai processor done | success=%d errors=%d",
                    sum(1 for e in enrichments if "error" not in e),
                    sum(1 for e in enrichments if "error" in e))
        return ProcessingResult(success=True, enrichments=enrichments)
