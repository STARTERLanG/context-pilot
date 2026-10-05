"""fetch_models / check_connection 单测。"""

import httpx
import pytest

from context_pilot.optimizer.openai_provider import (
    ProviderError,
    fetch_models,
    check_connection,
)


def test_fetch_models_returns_ids(monkeypatch):
    def fake_get(self, url, headers=None):
        assert url.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    assert fetch_models("https://x/v1", "sk-1") == ["a", "b"]


def test_fetch_models_401(monkeypatch):
    def fake_get(self, url, headers=None):
        return httpx.Response(401, json={})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    with pytest.raises(ProviderError, match="鉴权"):
        fetch_models("https://x/v1", "sk-bad")


def test_fetch_models_empty_data(monkeypatch):
    def fake_get(self, url, headers=None):
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    with pytest.raises(ProviderError, match="未返回任何"):
        fetch_models("https://x/v1", "sk-1")


def test_fetch_models_no_key():
    with pytest.raises(ProviderError, match="API Key"):
        fetch_models("https://x/v1", "")


def test_check_connection_success(monkeypatch):
    def fake_post(self, url, json=None, headers=None):
        assert url.endswith("/chat/completions")
        assert json["model"] == "m"
        assert json["max_tokens"] == 1
        return httpx.Response(200, json={"choices": []})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    elapsed = check_connection("https://x/v1", "sk-1", "m")
    assert elapsed >= 0


def test_check_connection_404(monkeypatch):
    def fake_post(self, url, json=None, headers=None):
        return httpx.Response(404, json={})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    with pytest.raises(ProviderError, match="模型不存在"):
        check_connection("https://x/v1", "sk-1", "m")


def test_check_connection_no_model():
    with pytest.raises(ProviderError, match="模型"):
        check_connection("https://x/v1", "sk-1", "")
