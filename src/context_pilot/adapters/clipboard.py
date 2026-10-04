"""剪贴板模式的 Agent 适配器（PRD 12 模式 A）。

三个适配器逻辑完全相同，仅 name 不同；为保持 PRD 的「每个 Agent 一个适配器」
结构，用工厂函数生成，避免三个近乎一样的类。
"""

from context_pilot.adapters.base import AgentAdapter
from context_pilot.platform.clipboard import write_clipboard_text


class ClipboardAdapter:
    """把文本写入剪贴板，由用户在目标 Agent 里粘贴。"""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def deliver(self, text: str) -> None:
        write_clipboard_text(text)

    def __repr__(self) -> str:
        return f"<ClipboardAdapter {self.name}>"


def claude() -> ClipboardAdapter:
    return ClipboardAdapter("claude")


def codex() -> ClipboardAdapter:
    return ClipboardAdapter("codex")


def gemini() -> ClipboardAdapter:
    return ClipboardAdapter("gemini")
