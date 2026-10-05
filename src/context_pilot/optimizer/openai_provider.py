"""OpenAI 兼容的 LLM 提供方。可接 OpenAI / DeepSeek / Qwen / Ollama / vLLM 等。

只依赖 httpx，不引入 SDK，便于对接任意兼容端点。密钥不出现在异常与日志中。
支持从 ProfileStore 按启用的配置加载（优先），也保留直接传参（测试用）。
"""

import httpx

from context_pilot.models.profiles import ProfileStore
from context_pilot.optimizer.templates import SYSTEM_PROMPT, build_user_message


class ProviderError(RuntimeError):
    """调用 LLM 失败。message 面向用户，不含密钥。"""




def fetch_models(base_url: str, api_key: str, timeout: float = 15.0) -> list[str]:
    """拉取 OpenAI 兼容端点的可用模型列表（GET /v1/models）。

    返回模型 ID 列表。任何失败抛 ProviderError（不含密钥）。
    """
    if not api_key:
        raise ProviderError("未填写 API Key")
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url.rstrip('/')}/models", headers=headers)
    except httpx.TimeoutException as exc:
        raise ProviderError(f"获取模型超时（{timeout}s）") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("无法连接服务，请检查 Base URL 与网络") from exc

    if response.status_code == 401:
        raise ProviderError("鉴权失败，请检查 API Key")
    if response.status_code >= 400:
        raise ProviderError(f"接口返回错误状态 {response.status_code}")

    try:
        data = response.json()
        models = [item.get("id") for item in data.get("data", [])]
    except (ValueError, AttributeError, TypeError) as exc:
        raise ProviderError("接口返回结构异常，缺少 data 列表") from exc

    ids = [m for m in models if isinstance(m, str) and m]
    if not ids:
        raise ProviderError("接口未返回任何可用模型")
    return ids


def check_connection(
    base_url: str, api_key: str, model: str, timeout: float = 15.0
) -> float:
    """连通性测试：发一个最小 chat 请求，成功返回耗时（秒）。

    只校验连通与鉴权，不要求生成完整内容（用极小 max_tokens）。
    """
    if not api_key:
        raise ProviderError("未填写 API Key")
    if not model:
        raise ProviderError("未选择模型")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    import time as _time

    started = _time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise ProviderError(f"连接超时（{timeout}s）") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("无法连接服务，请检查 Base URL 与网络") from exc

    elapsed = _time.monotonic() - started
    if response.status_code == 401:
        raise ProviderError("鉴权失败，请检查 API Key")
    if response.status_code == 404:
        raise ProviderError("模型不存在或接口路径不对")
    if response.status_code >= 400:
        raise ProviderError(f"接口返回错误状态 {response.status_code}")
    return round(elapsed, 2)


class OpenAiProvider:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        profile_store: ProfileStore | None = None,
    ) -> None:
        """优先用 profile_store 里启用的配置；否则用直接传入的参数。"""
        self._timeout = timeout
        self._profile_store = profile_store
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    def _resolve(self) -> tuple[str, str, str]:
        """返回 (base_url, api_key, model)。"""
        if self._profile_store is not None:
            enabled = self._profile_store.list_enabled()
            if enabled:
                profile = enabled[0]
                key = self._profile_store.reveal_key_by_id(profile.id)
                return profile.base_url, key, profile.model
        if self._base_url and self._api_key and self._model:
            return self._base_url, self._api_key, self._model
        raise ProviderError(
            "未配置有效的模型配置：请在设置中添加并启用一个模型配置，"
            "或传入 base_url/api_key/model"
        )

    async def enhance(self, prompt: str, context: str = "") -> str:
        base_url, api_key, model = self._resolve()
        if not api_key:
            raise ProviderError("未配置 LLM API Key，请检查模型配置")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(prompt, context)},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(f"调用 LLM 超时（{self._timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("无法连接 LLM 服务，请检查 base_url 与网络") from exc

        if response.status_code == 401:
            raise ProviderError("LLM 鉴权失败，请检查 api_key")
        if response.status_code >= 400:
            raise ProviderError(f"LLM 返回错误状态 {response.status_code}")

        return _extract_content(response)


def _extract_content(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError as exc:
        raise ProviderError("LLM 返回内容不是合法 JSON") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("LLM 返回结构异常，缺少 choices[0].message.content") from exc

    text = (content or "").strip()
    if not text:
        raise ProviderError("LLM 返回了空结果")
    return text
