"""External HTTP AI processor.

Generic adapter for agent runtimes that expose an HTTP surface (e.g.
KohakuTerrarium, dify, langflow, n8n, custom FastAPI workers). One POST
per record; the response JSON becomes that record's enrichment.

Required config:
    endpoint (str): full URL the processor POSTs to.

Optional config:
    timeout (float, default 60): per-request timeout in seconds.
    auth_header (str): full Authorization header value (e.g. "Bearer xyz").
    headers (dict): extra HTTP headers merged onto the request.
    agent_id (str): free-form identifier passed in the payload; useful when
        the external runtime hosts multiple agents (e.g. a KT creature name).
    send_record (bool, default True): include the full normalized_data in
        the payload alongside the rendered prompt. Set False if the remote
        side only needs the prompt.

Request body per record:
    {
        "prompt": "<rendered prompt>",
        "record": { ... normalized_data ... },   # if send_record
        "agent_id": "<agent_id>"                 # if set
    }

Response must be a JSON object; it is stored verbatim as the enrichment.
Non-2xx, non-JSON, or non-dict responses produce {"error": "<reason>"}
per record without aborting the batch.
"""

import json
import logging
import re
from typing import TYPE_CHECKING, Any

import httpx

from backend.processors.base import AbstractProcessor, ProcessingResult
from backend.processors.registry import register_processor

if TYPE_CHECKING:
    from backend.models.record import CollectedRecord

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, data: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), template)


@register_processor
class ExternalProcessor(AbstractProcessor):
    """Process records by POSTing each one to an external agent endpoint."""

    processor_type = "external_http"

    async def process(
        self,
        records: list["CollectedRecord"],
        prompt_template: str,
        config: dict[str, Any],
    ) -> ProcessingResult:
        endpoint = config.get("endpoint")
        if not endpoint:
            return ProcessingResult(
                success=False,
                error="external_http: 'endpoint' is required in config",
            )

        timeout = config.get("timeout", 60)
        auth_header = config.get("auth_header")
        extra_headers = config.get("headers") or {}
        agent_id = config.get("agent_id")
        send_record = config.get("send_record", True)

        headers = {"content-type": "application/json", **extra_headers}
        if auth_header:
            headers["authorization"] = auth_header

        logger.info(
            "external_http processor | endpoint=%s agent_id=%s records=%d",
            endpoint,
            agent_id or "(none)",
            len(records),
        )

        enrichments: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            for i, record in enumerate(records):
                prompt = _render(prompt_template, record.normalized_data)
                payload: dict[str, Any] = {"prompt": prompt}
                if send_record:
                    payload["record"] = record.normalized_data
                if agent_id:
                    payload["agent_id"] = agent_id

                try:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    resp.raise_for_status()
                    try:
                        enrichment = resp.json()
                    except json.JSONDecodeError:
                        enrichment = {"analysis": resp.text}
                    if not isinstance(enrichment, dict):
                        enrichment = {"analysis": enrichment}
                    logger.info(
                        "external_http resp [%d/%d] | preview=%s",
                        i + 1,
                        len(records),
                        str(enrichment)[:200],
                    )
                    enrichments.append(enrichment)
                except Exception as exc:
                    logger.error(
                        "external_http error [%d/%d] | %s", i + 1, len(records), exc
                    )
                    enrichments.append({"error": str(exc)})

        return ProcessingResult(success=True, enrichments=enrichments)
