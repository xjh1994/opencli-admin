"""Tests for messaging platform notifiers (Feishu, DingTalk, WeCom)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.notifiers.base import NotificationPayload
from backend.notifiers.registry import list_notifier_types


def _payload(**kwargs):
    return NotificationPayload(
        event="on_new_record",
        source_id="src-1",
        record_id="rec-1",
        data={"title": "Test Article", "source_id": "src-1"},
        **kwargs,
    )


def test_all_notifiers_registered():
    types = list_notifier_types()
    assert "feishu" in types
    assert "dingtalk" in types
    assert "wecom" in types
    assert "email" in types


# ── Feishu ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feishu_send_success():
    from backend.notifiers.feishu_notifier import FeishuNotifier

    notifier = FeishuNotifier()
    payload = _payload()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 0}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await notifier.send(
            {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc"},
            payload,
        )

    assert result is True


@pytest.mark.asyncio
async def test_feishu_send_failure():
    from backend.notifiers.feishu_notifier import FeishuNotifier

    notifier = FeishuNotifier()
    payload = _payload()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"StatusCode": 400, "StatusMessage": "forbidden"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await notifier.send({"webhook_url": "https://feishu.example.com"}, payload)

    assert result is False


@pytest.mark.asyncio
async def test_feishu_template_rendering():
    from backend.notifiers.feishu_notifier import FeishuNotifier

    notifier = FeishuNotifier()
    payload = _payload()

    captured = {}

    async def fake_post(url, json):
        captured["body"] = json
        resp = MagicMock()
        resp.json.return_value = {"StatusCode": 0}
        return resp

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_cls.return_value = mock_client

        await notifier.send(
            {"webhook_url": "https://feishu.ex.com", "title": "Alert: {{title}}"},
            payload,
        )

    assert "Alert: Test Article" in captured["body"]["content"]["post"]["zh_cn"]["title"]


# ── DingTalk ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dingtalk_send_success():
    from backend.notifiers.dingtalk_notifier import DingTalkNotifier

    notifier = DingTalkNotifier()
    payload = _payload()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await notifier.send(
            {"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=abc"},
            payload,
        )

    assert result is True


@pytest.mark.asyncio
async def test_dingtalk_send_with_sign():
    from backend.notifiers.dingtalk_notifier import DingTalkNotifier, _dingtalk_sign

    # Test sign generation
    sign = _dingtalk_sign("mysecret", 1700000000000)
    assert isinstance(sign, str)
    assert len(sign) > 0

    notifier = DingTalkNotifier()
    payload = _payload()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"errcode": 0}

    captured_url = {}

    async def fake_post(url, json):
        captured_url["url"] = url
        return mock_resp

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_cls.return_value = mock_client

        await notifier.send(
            {"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=x", "secret": "mysecret"},
            payload,
        )

    assert "timestamp=" in captured_url["url"]
    assert "sign=" in captured_url["url"]


# ── WeCom ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wecom_send_success():
    from backend.notifiers.wecom_notifier import WeComNotifier

    notifier = WeComNotifier()
    payload = _payload()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await notifier.send(
            {"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc"},
            payload,
        )

    assert result is True


@pytest.mark.asyncio
async def test_wecom_send_failure():
    from backend.notifiers.wecom_notifier import WeComNotifier

    notifier = WeComNotifier()
    payload = _payload()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"errcode": 60011, "errmsg": "not allow"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await notifier.send({"webhook_url": "https://qyapi.weixin.qq.com/x"}, payload)

    assert result is False
