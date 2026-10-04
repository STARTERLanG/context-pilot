"""Code Graph 的数据结构（PRD 20 的 edges 表）。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphEdge:
    """一条符号关系边：OrderService calls RefundService。"""

    source: str  # 源符号名
    target: str  # 目标符号名
    relation: str  # calls / inherits / references


@dataclass(frozen=True)
class SymbolRef:
    """一个符号及其在文件中的位置。"""

    name: str
    kind: str  # class / function / method / variable
    file: str  # 项目相对路径
    line: int
