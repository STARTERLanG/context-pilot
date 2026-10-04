"""记忆抽取与冲突检测单测。"""

from context_pilot.memory.extractor import extract, find_conflicts
from context_pilot.memory.models import MemoryType


def test_extract_architectural_decision():
    candidates = extract("所有业务逻辑必须经过 Service 层，禁止直接访问数据库")
    assert candidates
    assert all(c.type is MemoryType.ARCHITECTURE_DECISION for c in candidates)


def test_extract_user_preference():
    candidates = extract("不要用 npm 管理依赖，我们统一用 uv")
    assert any(c.type is MemoryType.USER_PREFERENCE for c in candidates)


def test_extract_project_fact():
    candidates = extract("本项目使用 FastAPI 作为后端框架，目标是稳定运行。")
    assert any(c.type is MemoryType.PROJECT_FACT for c in candidates)


def test_extract_ignores_short_plain_sentences():
    assert extract("好的，我知道了") == []


def test_extract_splits_multiple_sentences():
    candidates = extract("业务必须走 Service 层。不要用 npm，我们统一用 uv。")
    assert len(candidates) == 2
    assert candidates[0].type is MemoryType.ARCHITECTURE_DECISION
    assert candidates[1].type is MemoryType.USER_PREFERENCE


def test_find_conflicts_returns_similar_memory():
    conflicts = find_conflicts(
        ["退款逻辑必须独立于 OrderService"],
        "退款逻辑必须独立于 OrderService，不能写在 OrderService 里",
    )
    assert conflicts


def test_find_conflicts_empty_when_distinct():
    conflicts = find_conflicts(
        ["项目使用 FastAPI"],
        "所有业务逻辑必须经过 Service 层",
    )
    assert conflicts == []
