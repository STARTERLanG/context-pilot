"""引擎层单测：不依赖 QApplication，可在无 GUI 环境运行。"""

import asyncio

import pytest

from context_pilot.core.models import EnhancedPrompt
from context_pilot.core.pipeline import Pipeline
from context_pilot.core.ranking import RankingWeights
from context_pilot.memory.models import MemoryType
from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore
from context_pilot.retrieval.keyword import KeywordRetriever


def _make_project(tmp_path):
    (tmp_path / "AGENTS.md").write_text("业务逻辑必须放在 service 层", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    order = tmp_path / "src" / "order"
    order.mkdir(parents=True)
    (order / "service.py").write_text("class OrderService:\n    pass\n", encoding="utf-8")
    return tmp_path


def test_enhance_returns_enhanced_prompt(tmp_path):
    project = _make_project(tmp_path)
    result = asyncio.run(Pipeline(project_root=project).enhance("修一下 order 接口"))

    assert isinstance(result, EnhancedPrompt)
    assert result.original_prompt == "修一下 order 接口"
    assert "## Objective" in result.enhanced_prompt
    assert "修一下 order 接口" in result.enhanced_prompt


def test_enhance_collects_rules_and_code_as_context(tmp_path):
    project = _make_project(tmp_path)
    result = asyncio.run(Pipeline(project_root=project).enhance("修一下 order 接口"))

    sources = [item.source for item in result.context]
    assert "AGENTS.md" in sources
    assert any("service.py" in source for source in sources)
    # 规则文件不应再以 code 类型重复出现
    assert sources.count("AGENTS.md") == 1
    assert all(
        item.type == "rule"
        for item in result.context
        if item.source == "AGENTS.md"
    )


def test_enhance_empty_prompt_raises_value_error(tmp_path):
    project = _make_project(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(Pipeline(project_root=project).enhance("   "))


def test_enhance_accepts_injected_weights(tmp_path):
    project = _make_project(tmp_path)
    weights = RankingWeights(semantic=1.0, path=0.0, symbol=0.0)
    result = asyncio.run(
        Pipeline(project_root=project, weights=weights).enhance("order 接口")
    )
    assert result.context


def test_enhance_includes_memory_when_retriever_injected(tmp_path):
    project = _make_project(tmp_path)
    store = MemoryStore(project, base_dir=tmp_path / "memroot")
    store.add("OrderService 不得直接依赖 RefundService", MemoryType.ARCHITECTURE_DECISION)

    pipeline = Pipeline(
        project_root=project,
        retrievers=[KeywordRetriever(), MemoryRetriever(store)],
    )
    result = asyncio.run(pipeline.enhance("修改 OrderService 逻辑"))

    memory_items = [item for item in result.context if item.type == "memory"]
    assert len(memory_items) == 1
    assert "OrderService" in memory_items[0].content
