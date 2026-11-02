"""LLM 提供方抽象。本轮只有 Stub，真实提供方（OpenAI 兼容）后续接入。

调用点已按 PRD 定为 async，避免换真实模型时把网络调用写死在 UI 回调里。
"""

from typing import Protocol


class LlmProvider(Protocol):
    """把原始 prompt 变成增强后的工程任务 prompt。"""

    async def enhance(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 6000,
        style: str = "default",
        styles=None,
        standalone: bool = False,
    ) -> str: ...


class StubProvider:
    """不联网的假提供方，返回结构固定的增强结果，用于打通链路与写稳定测试。

    输出按优化模式（mode）区分骨架：
    - task（结构化增强）：目标 + 实现步骤 + 验收标准（任务书骨架）。
    - basic / professional / planning：直接返回原文（代表「优化后的提示词文本」，
      最简占位，不模拟真实润色/精准化/步骤化细节）。

    注意：task 骨架的固定标题是「最简占位」，不代表真实 LLM 输出的全部形态——
    真实输出遵循对应 SYSTEM_PROMPT 的「按需组织」。测试断言依赖这些标题
    （如 `## 目标`），改动 Stub 骨架需同步检查 test_provider.py。
    """

    async def enhance(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 6000,
        style: str = "default",
        styles=None,
        standalone: bool = False,
    ) -> str:
        from context_pilot.optimizer.templates import resolve_mode

        mode = resolve_mode(style, styles)

        # 无项目（standalone）或非 task 模式：返回原文（代表优化后的提示词文本）
        if standalone or mode != "task":
            return prompt

        has_context = bool(context.strip())
        blocks = [
            "## 目标",
            "",
            prompt,
            "",
            "## 实现步骤",
            "",
            "1. 明确本次改动的目标行为与边界。",
            "2. 定位相关代码与既有实现模式。",
        ]
        if has_context:
            blocks.append("3. 遵循项目已有约定，复用现有抽象与命名。")
        blocks += [
            "4. 完成改动并补充对应测试。",
            "",
            "## 验收标准",
            "",
            "- [ ] 相关测试通过。",
        ]
        return "\n".join(blocks)
