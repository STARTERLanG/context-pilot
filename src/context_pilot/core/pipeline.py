"""最简增强编排。

本轮不接检索：把 prompt 交给 provider 直接生成增强结果。
后续规则/检索接入时，在 enhance 内组装 ContextItem 再传 provider，UI 无需改动。
"""

from context_pilot.core.models import EnhanceOptions, EnhancedPrompt
from context_pilot.optimizer.provider import LlmProvider, StubProvider


class Pipeline:
    """把原始 prompt 变成 EnhancedPrompt 的单一入口。"""

    def __init__(self, provider: LlmProvider | None = None) -> None:
        self._provider: LlmProvider = provider or StubProvider()

    async def enhance(
        self, prompt: str, options: EnhanceOptions | None = None
    ) -> EnhancedPrompt:
        text = prompt.strip()
        if not text:
            raise ValueError("prompt 不能为空")

        enhanced = await self._provider.enhance(text)
        return EnhancedPrompt(original_prompt=prompt, enhanced_prompt=enhanced)
