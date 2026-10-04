"""核心数据结构。字段沿用 PRD 7.2 的 ContextItem 约定。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextItem:
    """一条进入增强上下文的材料（规则/代码/文档等）。"""

    id: str
    type: str
    source: str
    content: str
    relevance: float = 0.0
    priority: int = 0
    path: str | None = None
    token_cost: int = 0


@dataclass(frozen=True)
class EnhanceOptions:
    """单次增强的可调参数。本轮只有占位字段，接真实模型时再扩充。"""

    max_tokens: int = 6000


@dataclass(frozen=True)
class EnhancedPrompt:
    """一次增强的完整结果，供 UI 展示与写回剪贴板。"""

    original_prompt: str
    enhanced_prompt: str
    context: list[ContextItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
