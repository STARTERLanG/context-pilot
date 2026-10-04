"""OpenAI 兼容提供方单测。用 httpx MockTransport，不发起真实网络请求。"""

import asyncio

import httpx
import pytest

from context_pilot.optimizer.openai_provider import (
    OpenAiProvider,
    ProviderError,
    _extract_content,
)
from context_pilot.optimizer.templates import SYSTEM_PROMPT, build_user_message


def _response(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_enhance_returns_content(monkeypatch):
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")

    async def fake_post(self, url, json=None, headers=None):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer sk-test"
        assert json["messages"][0]["content"] == SYSTEM_PROMPT
        return _response("## Objective\n\n做点什么")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = asyncio.run(provider.enhance("做点什么", context="<rule>a</rule>"))
    assert result == "## Objective\n\n做点什么"


def test_enhance_without_api_key_raises():
    provider = OpenAiProvider("https://x/v1", "", "m")
    with pytest.raises(ProviderError, match="API Key"):
        asyncio.run(provider.enhance("x"))


def test_enhance_401_mentions_auth(monkeypatch):
    provider = OpenAiProvider("https://x/v1", "sk-bad", "m")

    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(401, json={"error": "bad key"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ProviderError, match="鉴权"):
        asyncio.run(provider.enhance("x"))


def test_enhance_timeout_raises_provider_error(monkeypatch):
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")

    async def fake_post(self, url, json=None, headers=None):
        raise httpx.TimeoutException("too slow")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ProviderError, match="超时"):
        asyncio.run(provider.enhance("x"))


def test_extract_content_missing_choices_raises():
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json={"choices": []}))


def test_extract_content_empty_raises():
    with pytest.raises(ProviderError, match="空结果"):
        _extract_content(_response("   "))


def test_build_user_message_wraps_request_and_context():
    message = build_user_message("修一下", "<rule>x</rule>")
    assert "<user_request>" in message
    assert "修一下" in message
    assert "<project_context>" in message
