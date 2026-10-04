"""按激活策略筛选规则。对齐 PRD 6.3。

本轮实现 ALWAYS；FILE_MATCH / SEMANTIC 保留分支，待格式定义后填充。
"""

from context_pilot.rules.models import Activation, Rule


def select(rules: list[Rule], files: list[str] | None = None) -> list[Rule]:
    """返回当前上下文应加入的规则，按优先级降序。

    files 为本次检索命中的文件路径；后续 FILE_MATCH 规则会用到。
    """
    files = files or []
    selected: list[Rule] = []

    for rule in rules:
        if rule.activation is Activation.ALWAYS:
            selected.append(rule)
        elif rule.activation is Activation.FILE_MATCH:
            # 扩展点：待规则格式定义后，用 rule.match_pattern 匹配 files
            continue
        elif rule.activation is Activation.MANUAL:
            # 扩展点：待支持用户显式 @rule 调用
            continue

    selected.sort(key=lambda r: r.priority, reverse=True)
    return selected
