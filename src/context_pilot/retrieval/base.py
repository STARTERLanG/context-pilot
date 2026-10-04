"""检索器抽象。

PRD 6.5 规划了多级检索（ripgrep → 路径 → AST → 向量 → 图扩展）。
定义此协议后，新增检索器只需实现 search，Pipeline 无需改动。
"""

from typing import Protocol, runtime_checkable

from context_pilot.core.models import ContextItem
from context_pilot.project.models import ProjectContext


@runtime_checkable
class Retriever(Protocol):
    """把自然语言查询映射为候选上下文项。"""

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]: ...
