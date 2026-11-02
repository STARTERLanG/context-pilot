"""OpenAI 兼容的 LLM 提供方。可接 OpenAI / DeepSeek / Qwen / Ollama / vLLM 等。

只依赖 httpx，不引入 SDK，便于对接任意兼容端点。密钥不出现在异常与日志中。
支持从 ProfileStore 按启用的配置加载（优先），也保留直接传参（测试用）。
"""

import httpx

from context_pilot.models.profiles import ProfileStore
from context_pilot.optimizer.templates import (
    STANDALONE_SYSTEM_PROMPT,
    build_user_message,
    resolve_mode,
    mode_system_prompt,
)


class ProviderError(RuntimeError):
    """调用 LLM 失败。message 面向用户，不含密钥。"""


# 拉取模型列表（GET /v1/models）的超时上限。端点响应慢或网络不通时，
# 超过此时长即抛「超时」并释放线程，避免设置页/主页面一直停在「加载中」。
MODELS_FETCH_TIMEOUT = 15.0


def fetch_models(
    base_url: str, api_key: str, timeout: float = MODELS_FETCH_TIMEOUT
) -> list[str]:
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
        temperature: float = 1.0,
        profile_store: ProfileStore | None = None,
    ) -> None:
        """用直接传入的参数；profile_store 仅在未传参时作为后备来源。

        调用方（装配层）应当已按用户选定的增强目标传齐三项——「用哪条配置」
        由用户决定，本类不再自行挑一条生效配置。
        """
        self._timeout = timeout
        self._temperature = temperature
        self._profile_store = profile_store
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    def _resolve(self) -> tuple[str, str, str, float]:
        """返回 (base_url, api_key, model, temperature)。"""
        if self._base_url and self._api_key and self._model:
            return self._base_url, self._api_key, self._model, self._temperature
        if self._profile_store is not None:
            # 兼容仅传 profile_store 的构造：只在恰好一条生效配置时可用。
            # 多条生效时无法判断用户意图，宁可报错也不替用户猜。
            enabled = self._profile_store.list_enabled()
            if len(enabled) == 1:
                profile = enabled[0]
                key = self._profile_store.reveal_key_by_id(profile.id)
                return profile.base_url, key, profile.model, profile.temperature
        raise ProviderError(
            "未配置可用的增强目标：请先在设置页启用模型配置，"
            "再在主页面「模型」下拉中选定本次增强使用的模型"
        )

    async def enhance(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 6000,
        style: str = "default",
        styles=None,
        standalone: bool = False,
    ) -> str:
        base_url, api_key, model, temperature = self._resolve()
        if not api_key:
            raise ProviderError("未配置 LLM API Key，请检查模型配置")

        # standalone（无项目）固定走「基础优化」取向；否则按 style（=模式 key）
        # 解析出 mode，选择对应的 system prompt（task/basic/professional/planning）。
        if standalone:
            system = STANDALONE_SYSTEM_PROMPT
        else:
            system = mode_system_prompt(resolve_mode(style, styles))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": build_user_message(
                        prompt, context, style, styles, standalone=standalone
                    ),
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
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

    content = _pick_content(data)
    if content is _MISSING:
        raise ProviderError("LLM 返回结构异常，缺少 choices[0].message.content")

    text = str(content or "").strip()
    if not text:
        raise ProviderError("LLM 返回了空结果")
    return text


_MISSING = object()


def _pick_content(data):
    """从 OpenAI 兼容响应里稳健地取出文本内容。

    返回值语义：
    - 结构异常（choices 缺失/为空、元素非 dict、message 非 dict、缺 content 字段）
      → 返回 _MISSING 哨兵，由调用方报「结构异常」；
    - 字段存在但值为 None/空 → 原样返回 None，由调用方报「空结果」。

    这样能把「接口根本没给这个字段」（结构漂移）与「给了但内容是空的」（正常空回复）
    两种情形区分开，避免误报，也避免逐层抛含义不明的 KeyError/TypeError。
    """
    if not isinstance(data, dict):
        return _MISSING
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return _MISSING
    first = choices[0]
    if not isinstance(first, dict):
        return _MISSING
    message = first.get("message")
    if not isinstance(message, dict):
        return _MISSING
    if "content" not in message:
        return _MISSING
    return message["content"]
