"""增强编排：把规则、检索、排序组装成一次增强。

各模块通过依赖注入进入（provider / retriever 均可替换），Pipeline 只依赖抽象，
不 import 任何具体实现之外的东西——新增检索器无需改动本文件。
"""

from collections.abc import Sequence
from pathlib import Path

from context_pilot.core.models import ContextItem, EnhanceOptions, EnhancedPrompt
from context_pilot.core.ranking import RankingWeights, rank
from context_pilot.optimizer.provider import LlmProvider, StubProvider
from context_pilot.project.models import ProjectContext
from context_pilot.project.scanner import scan
from context_pilot.retrieval.base import Retriever
from context_pilot.retrieval.keyword import KeywordRetriever
from context_pilot.rules.loader import load as load_rules
from context_pilot.rules.matcher import select as select_rules
from context_pilot.rules.models import Rule

_MAX_CONTEXT_CHARS = 6000


def _rule_to_item(rule: Rule) -> ContextItem:
    return ContextItem(
        id=f"rule:{rule.source}",
        type="rule",
        source=rule.source,
        content=rule.content,
        priority=rule.priority,
        path=str(rule.path) if rule.path else None,
        reason=f"项目规则，优先级 {rule.priority}，激活策略 {rule.activation.value}",
    )


def _render_context(items: list[ContextItem]) -> str:
    """把上下文项渲染成给模型的纯文本块，总长受预算约束。"""
    blocks: list[str] = []
    used = 0
    for item in items:
        block = f"[{item.type}] {item.source}\n{item.content}"
        if used + len(block) > _MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


class Pipeline:
    """把原始 prompt 变成 EnhancedPrompt 的单一入口。"""

    def __init__(
        self,
        project_root: Path | str | None = None,
        provider: LlmProvider | None = None,
        weights: RankingWeights | None = None,
        retrievers: Sequence[Retriever] | None = None,
    ) -> None:
        self._project: ProjectContext = scan(Path(project_root or Path.cwd()))
        self._provider: LlmProvider = provider or StubProvider()
        self._weights = weights
        # retrievers 为扩展点：新增检索来源（代码/记忆/后续向量）只需追加，
        # 无需改动 enhance。默认仅代码检索。
        self._retrievers: list[Retriever] = (
            list(retrievers) if retrievers is not None else [KeywordRetriever()]
        )

    async def enhance(
        self, prompt: str, options: EnhanceOptions | None = None
    ) -> EnhancedPrompt:
        text = prompt.strip()
        if not text:
            raise ValueError("prompt 不能为空")

        rules = select_rules(load_rules(self._project.root))
        rule_sources = {rule.source for rule in rules}
        # 规则文件已作为 rule 进入上下文，避免检索器再以 code 重复收录
        retrieved: list[ContextItem] = []
        for retriever in self._retrievers:
            retrieved.extend(retriever.search(text, self._project))
        code_items = [
            item for item in retrieved if item.source not in rule_sources
        ]
        items = rank(
            [_rule_to_item(rule) for rule in rules] + code_items, self._weights
        )

        enhanced = await self._provider.enhance(text, _render_context(items))
        return EnhancedPrompt(
            original_prompt=prompt,
            enhanced_prompt=enhanced,
            context=items,
        )
