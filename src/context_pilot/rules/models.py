"""规则的数据结构与激活策略。对齐 PRD 6.3。"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Activation(str, Enum):
    """规则何时加入上下文。"""

    ALWAYS = "always"  # 始终加入：代码风格、安全规范、架构原则
    FILE_MATCH = "file_match"  # 仅当相关文件出现时
    SEMANTIC = "semantic"  # 由模型/嵌入判断相关性（后续实现）
    MANUAL = "manual"  # 用户显式调用


@dataclass(frozen=True)
class Rule:
    """一条从项目规则文件解析出的规则。"""

    source: str
    content: str
    activation: Activation = Activation.ALWAYS
    priority: int = 100
    path: Path | None = None
    match_pattern: str | None = None  # Activation.FILE_MATCH 时用于匹配文件路径
