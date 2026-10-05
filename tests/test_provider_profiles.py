"""Provider 从 ProfileStore 加载启用配置的单测。"""

import asyncio

import httpx
import pytest

from context_pilot.models.profiles import ProfileStore
from context_pilot.optimizer.openai_provider import OpenAiProvider, ProviderError


def _profile_store(tmp_path) -> ProfileStore:
    store = ProfileStore(base_dir=tmp_path)
    store.add(
        name="deepseek",
        provider="openai",
        base_url="https://api.deepseek.com/v1",
        api_key="sk-topsecret-123456",
        model="deepseek-chat",
        temperature=0.2,
        max_tokens=8000,
        enabled=True,
    )
    return store


def test_provider_uses_enabled_profile(monkeypatch, tmp_path):
    store = _profile_store(tmp_path)
    provider = OpenAiProvider(profile_store=store)

    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["auth"] = headers["Authorization"]
        captured["model"] = json["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = asyncio.run(provider.enhance("hi"))

    assert result == "ok"
    assert captured["url"].endswith("/chat/completions")
    assert captured["auth"] == "Bearer sk-topsecret-123456"  # 明文只在内部
    assert captured["model"] == "deepseek-chat"


def test_provider_no_enabled_profile_raises(tmp_path):
    store = ProfileStore(base_dir=tmp_path)  # 空库，无启用配置
    provider = OpenAiProvider(profile_store=store)

    with pytest.raises(ProviderError, match="未配置"):
        asyncio.run(provider.enhance("hi"))


def test_provider_direct_params_still_work(monkeypatch):
    provider = OpenAiProvider(
        base_url="https://x/v1", api_key="sk-direct", model="m", timeout=30
    )

    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert asyncio.run(provider.enhance("hi")) == "ok"
