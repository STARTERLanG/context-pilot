"""OpenAI 兼容的 LLM 提供方。可接 OpenAI / DeepSeek / Qwen / Ollama / vLLM 等。

只依赖 httpx，不引入 SDK，便于对接任意兼容端点。密钥不出现在异常与日志中。
"""

import httpx

from context_pilot.optimizer.templates import SYSTEM_PROMPT, build_user_message


class ProviderError(RuntimeError):
    """调用 LLM 失败。message 面向用户，不含密钥。"""


class OpenAiProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def enhance(self, prompt: str, context: str = "") -> str:
        if not self._api_key:
            raise ProviderError(
                "未配置 LLM API Key，请在 ~/.context-pilot/config.toml 中填写 llm.api_key"
            )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(prompt, context)},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(f"调用 LLM 超时（{self._timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("无法连接 LLM 服务，请检查 base_url 与网络") from exc

        if response.status_code == 401:
            raise ProviderError("LLM 鉴权失败，请检查 llm.api_key")
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
