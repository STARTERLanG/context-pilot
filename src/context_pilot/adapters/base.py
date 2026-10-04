"""Agent 适配器抽象。核心引擎与 Agent 完全解耦（PRD 11）。

Adapter 负责「把增强后的 Prompt 交给目标 Agent」。第一版统一用剪贴板模式
（PRD 12 模式 A：写入剪贴板，用户粘贴），不侵入 TUI。
命令行/PTY 模式是后续扩展点。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AgentAdapter(Protocol):
    """把文本注入目标 Coding Agent。"""

    name: str

    def deliver(self, text: str) -> None: ...
