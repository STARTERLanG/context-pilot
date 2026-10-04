"""LLM 提供方抽象。本轮只有 Stub，真实提供方（OpenAI 兼容）后续接入。

调用点已按 PRD 定为 async，避免换真实模型时把网络调用写死在 UI 回调里。
"""

from typing import Protocol


class LlmProvider(Protocol):
    """把原始 prompt 变成增强后的工程任务 prompt。"""

    async def enhance(self, prompt: str, context: str = "") -> str: ...


class StubProvider:
    """不联网的假提供方，返回结构固定的增强结果，用于打通链路与写稳定测试。"""

    async def enhance(self, prompt: str, context: str = "") -> str:
        return (
            "## Objective\n\n"
            f"{prompt}\n\n"
            "## Requirements\n\n"
            "1. 遵循项目已有的分层与命名约定。\n"
            "2. 不改动无关代码。\n"
            "3. 补充对应测试。\n\n"
            "## Acceptance Criteria\n\n"
            "- [ ] 目标行为可用。\n"
            "- [ ] 既有功能保持兼容。\n"
        )
