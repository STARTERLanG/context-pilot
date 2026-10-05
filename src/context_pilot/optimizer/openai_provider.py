"""OpenAI 兼容的 LLM 提供方。可接 OpenAI / DeepSeek / Qwen / Ollama / vLLM 等。

只依赖 httpx，不引入 SDK，便于对接任意兼容端点。密钥不出现在异常与日志中。
支持从 ProfileStore 按启用的配置加载（优先），也保留直接传参（测试用）。
"""

import httpx

from context_pilot.models.profiles import ProfileStore
from context_pilot.optimizer.templates import SYSTEM_PROMPT, build_user_message


class ProviderError(RuntimeError):
    """调用 LLM 失败。message 面向用户，不含密钥。"""


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
