"""项目记忆的数据结构。对齐 PRD 8.2 / 8.3。"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """PRD 8.2 的四类长期知识。"""

    PROJECT_FACT = "project_fact"  # 项目事实，如「项目使用 FastAPI」
    ARCHITECTURE_DECISION = "architecture_decision"  # 架构决策
    USER_PREFERENCE = "user_preference"  # 用户偏好
    HISTORICAL_DECISION = "historical_decision"  # 历史任务结论


@dataclass(frozen=True)
class Memory:
    """一条持久化的项目记忆。"""

    id: str
    type: MemoryType
    content: str
    scope: str = "project"
    source: str = "manual"
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")
