"""Unit tests for external_http processor."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.processors.external_processor import ExternalProcessor
from backend.processors.registry import get_processor


def _make_record(normalized: dict) -> SimpleNamespace:
    return SimpleNamespace(normalized_data=normalized)


def _mock_async_client(post_side_effect):
    client = MagicMock()
    client.post = AsyncMock(side_effect=post_side_effect)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


def _mock_response(status_code: int, json_body=None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    else:
        resp.json = MagicMock(side_effect=ValueError("not json"))
    if 200 <= status_code < 300:
        resp.raise_for_status = MagicMock()
    else:
        resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=resp
            )
        )
    return resp


def test_external_processor_registered():
    proc = get_processor("external_http")
    assert proc.processor_type == "external_http"
    assert isinstance(proc, ExternalProcessor)


@pytest.mark.asyncio
async def test_missing_endpoint_returns_error():
    proc = ExternalProcessor()
    result = await proc.process([_make_record({"title": "x"})], "p", {})
    assert result.success is False
    assert "endpoint" in (result.error or "")


@pytest.mark.asyncio
async def test_happy_path_renders_prompt_and_returns_enrichment():
    proc = ExternalProcessor()
    records = [_make_record({"title": "Hello", "content": "Body"})]
    resp = _mock_response(200, {"tags": ["news"], "summary": "OK"})
    ctx, client = _mock_async_client(post_side_effect=[resp])

    with patch("backend.processors.external_processor.httpx.AsyncClient", return_value=ctx):
        result = await proc.process(
            records, "T={{title}} C={{content}}", {"endpoint": "http://x/process"}
        )

    assert result.success is True
    assert result.enrichments == [{"tags": ["news"], "summary": "OK"}]
    call = client.post.await_args
    assert call.args[0] == "http://x/process"
    payload = call.kwargs["json"]
    assert payload["prompt"] == "T=Hello C=Body"
    assert payload["record"] == {"title": "Hello", "content": "Body"}
    assert "agent_id" not in payload


@pytest.mark.asyncio
async def test_agent_id_and_auth_propagate():
    proc = ExternalProcessor()
    records = [_make_record({"title": "x"})]
    resp = _mock_response(200, {"ok": True})
    ctx, client = _mock_async_client(post_side_effect=[resp])

    with patch("backend.processors.external_processor.httpx.AsyncClient", return_value=ctx):
        await proc.process(
            records,
            "t",
            {
                "endpoint": "http://x",
                "agent_id": "tagger-v1",
                "auth_header": "Bearer abc",
                "headers": {"x-trace": "1"},
                "send_record": False,
            },
        )

    call = client.post.await_args
    assert call.kwargs["json"]["agent_id"] == "tagger-v1"
    assert "record" not in call.kwargs["json"]
    headers = call.kwargs["headers"]
    assert headers["authorization"] == "Bearer abc"
    assert headers["x-trace"] == "1"


@pytest.mark.asyncio
async def test_per_record_error_does_not_abort_batch():
    proc = ExternalProcessor()
    records = [_make_record({"title": "a"}), _make_record({"title": "b"})]
    ok_resp = _mock_response(200, {"summary": "good"})
    bad_resp = _mock_response(500, text="boom")
    ctx, _client = _mock_async_client(post_side_effect=[bad_resp, ok_resp])

    with patch("backend.processors.external_processor.httpx.AsyncClient", return_value=ctx):
        result = await proc.process(records, "t", {"endpoint": "http://x"})

    assert result.success is True
    assert "error" in result.enrichments[0]
    assert result.enrichments[1] == {"summary": "good"}


@pytest.mark.asyncio
async def test_non_dict_json_wrapped_in_analysis():
    proc = ExternalProcessor()
    records = [_make_record({"title": "x"})]
    resp = _mock_response(200, ["tag-a", "tag-b"])
    ctx, _client = _mock_async_client(post_side_effect=[resp])

    with patch("backend.processors.external_processor.httpx.AsyncClient", return_value=ctx):
        result = await proc.process(records, "t", {"endpoint": "http://x"})

    assert result.enrichments[0] == {"analysis": ["tag-a", "tag-b"]}
