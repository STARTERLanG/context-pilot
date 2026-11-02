"""PreviewModel 信号语义单测（无 GUI 依赖的 QObject 测试需 QCoreApplication）。"""

import pytest
from PySide6.QtCore import QCoreApplication

from context_pilot.core.models import ContextItem, EnhancedPrompt
from context_pilot.ui.preview_model import PreviewModel


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


def test_initial_original_is_empty(qapp):
    model = PreviewModel()
    assert model.originalPrompt == ""


def test_begin_emits_session_started_but_not_for_result(qapp):
    model = PreviewModel()
    sessions = []
    changes = []
    model.sessionStarted.connect(lambda: sessions.append(1))
    model.changed.connect(lambda: changes.append(1))

    model.begin("剪贴板残留内容")

    assert model.originalPrompt == "剪贴板残留内容"
    assert len(sessions) == 1  # begin 触发 sessionStarted
    assert len(changes) == 1   # begin 也触发 changed（供 UI 刷新）

    # set_result 只触发 changed，不触发 sessionStarted
    model.set_result(EnhancedPrompt(original_prompt="剪贴板残留内容", enhanced_prompt="## Objective"))
    assert len(sessions) == 1  # 不增加
    assert len(changes) == 2


def test_set_result_keeps_original(qapp):
    model = PreviewModel()
    model.begin("A")
    model.set_result(EnhancedPrompt(original_prompt="A", enhanced_prompt="B"))
    # 增强完成后 original 仍是 A（输入框不应被重置为别的值）
    assert model.originalPrompt == "A"


def test_set_failed_does_not_touch_original(qapp):
    model = PreviewModel()
    model.begin("A")
    model.set_failed("LLM 超时")
    assert model.originalPrompt == "A"


def test_load_populates_without_enhancing(qapp):
    """取消自动增强：load 只载入内容，状态保持「就绪」，不触发 enhanceRequested。"""
    model = PreviewModel()
    requested = []
    model.enhanceRequested.connect(lambda t: requested.append(t))

    model.load("剪贴板内容")

    assert model.originalPrompt == "剪贴板内容"
    assert model.status == "就绪"
    assert model.enhancedPrompt == ""
    assert requested == []


def test_enhance_slot_requests_backend_and_marks_busy(qapp):
    """「增强」按钮链路：enhance() 发 enhanceRequested 供装配层跑管线。"""
    model = PreviewModel()
    requested = []
    model.enhanceRequested.connect(lambda t: requested.append(t))

    model.enhance("手动输入的指令")

    assert requested == ["手动输入的指令"]
    assert model.status == "正在增强…"
    assert model.originalPrompt == "手动输入的指令"


def test_enhance_with_blank_text_rejects(qapp):
    """空指令点「增强」：不请求后端，只提示失败。"""
    model = PreviewModel()
    requested = []
    model.enhanceRequested.connect(lambda t: requested.append(t))

    model.enhance("   \n  ")

    assert requested == []
    assert model.status.startswith("失败")


def test_enhance_ignores_duplicate_while_enhancing(qapp):
    """防重复点击：增强进行中再次触发被忽略，不重复请求后端。"""
    model = PreviewModel()
    requested = []
    model.enhanceRequested.connect(lambda t: requested.append(t))

    model.enhance("第一次指令")
    assert model.enhancing is True
    assert requested == ["第一次指令"]

    # 增强尚未完成，重复触发应被忽略
    model.enhance("第二次指令")
    assert requested == ["第一次指令"]  # 不新增

    # 完成后复位，可再次增强
    model.set_result(EnhancedPrompt(original_prompt="第一次指令", enhanced_prompt="结果"))
    assert model.enhancing is False
    model.enhance("第三次指令")
    assert requested == ["第一次指令", "第三次指令"]


def test_set_failed_resets_enhancing(qapp):
    """增强失败也复位，允许重试。"""
    model = PreviewModel()
    model.enhance("指令")
    assert model.enhancing is True
    model.set_failed("超时")
    assert model.enhancing is False


# ── 历史记录 ──────────────────────────────────────────────────────────


def test_history_records_newest_first(qapp):
    """每次成功的增强追加一条，新记录在前；失败不记录。"""
    model = PreviewModel()
    model.set_result(EnhancedPrompt(original_prompt="第一条", enhanced_prompt="A"))
    model.set_failed("超时")
    model.set_result(EnhancedPrompt(original_prompt="第二条", enhanced_prompt="B"))

    assert [h["original"] for h in model.history] == ["第二条", "第一条"]
    assert model.history[0]["enhanced"] == "B"


def test_history_keys_are_stable_identifiers(qapp):
    """每条记录带唯一且单调递增的 key。

    界面用它标识「展开的是哪一条」：新记录插在最前会让下标整体后移，
    用下标展开的条目会悄悄换成别人。
    """
    model = PreviewModel()
    for i in range(3):
        model.set_result(EnhancedPrompt(original_prompt=f"指令 {i}", enhanced_prompt="结果"))

    keys = [h["key"] for h in model.history]
    assert len(set(keys)) == 3
    assert keys == sorted(keys, reverse=True)  # 最新的 key 最大
    assert keys[0] == 3  # 不因重启以外的原因回绕


# ── Token 预算（PRD 二十六章 / 10.3）──────────────────────────────────


def test_token_stats_carry_budget(qapp):
    """预算随结果下发：UI 的占比要用本次实际生效的值，不能自己写死。"""
    model = PreviewModel()
    model.begin("A")
    model.set_result(
        EnhancedPrompt(original_prompt="A", enhanced_prompt="B", budget_tokens=6000)
    )
    assert model.tokenStats["budget"] == 6000


def test_token_stats_default_budget_is_zero(qapp):
    """未带预算的结果：budget 为 0，表示「未知上限」。"""
    model = PreviewModel()
    model.begin("A")
    model.set_result(EnhancedPrompt(original_prompt="A", enhanced_prompt="B"))
    assert model.tokenStats["budget"] == 0
    assert model.overBudget is False


def test_over_budget_flag(qapp):
    """合计超出预算时置位告警；预算内不置位。"""
    model = PreviewModel()
    model.begin("A")

    model.set_result(
        EnhancedPrompt(original_prompt="A", enhanced_prompt="B", budget_tokens=6000)
    )
    assert model.overBudget is False

    # 逼近预算：用长文本撑到明显超过 10 token
    filler = "这个词会被算进 token " * 40
    model.set_result(
        EnhancedPrompt(
            original_prompt=filler, enhanced_prompt=filler, budget_tokens=10
        )
    )
    assert model.tokenStats["total"] > 10
    assert model.overBudget is True


def test_over_budget_ignores_zero_budget(qapp):
    """陷阱：预算未知（0）时不能判定超限，否则 UI 会显示「超预算 inf%」。"""
    model = PreviewModel()
    model.begin("A")
    filler = "内容很长很长 " * 100
    model.set_result(
        EnhancedPrompt(original_prompt=filler, enhanced_prompt=filler, budget_tokens=0)
    )
    assert model.tokenStats["total"] > 0
    assert model.overBudget is False


def test_begin_keeps_previous_budget(qapp):
    """增强期间预算不清零：状态栏不应在等待时闪一下「无预算」。"""
    model = PreviewModel()
    model.begin("A")
    model.set_result(
        EnhancedPrompt(original_prompt="A", enhanced_prompt="B", budget_tokens=6000)
    )
    model.begin("新指令")
    assert model.tokenStats["budget"] == 6000


# ── Edit 增强结果（PRD 第三十八章 MVP「✓ Edit」）────────────────────────


def test_result_ready_only_on_success(qapp):
    """resultReady 只在增强成功时发；失败时不能发，否则会冲掉用户编辑中的内容。"""
    model = PreviewModel()
    fired = []
    model.resultReady.connect(lambda: fired.append(1))

    model.begin("A")
    model.set_failed("LLM 超时")
    assert fired == []

    model.set_result(EnhancedPrompt(original_prompt="A", enhanced_prompt="B"))
    assert len(fired) == 1


def test_use_sends_ui_text_not_model_value(qapp):
    """use() 带的是结果框当前文本：用户编辑过的内容必须被带走。"""
    model = PreviewModel()
    sent = []
    model.useRequested.connect(sent.append)

    model.begin("A")
    model.set_result(EnhancedPrompt(original_prompt="A", enhanced_prompt="原始增强结果"))
    model.use("用户改过的增强结果")

    assert sent == ["用户改过的增强结果"]
    # 同步回模型：后续复制 / 发送到 Agent 也用编辑后的版本
    assert model.enhancedPrompt == "用户改过的增强结果"


def test_use_ignores_blank_text(qapp):
    """空白内容不应触发使用（避免误把空串写进剪贴板）。"""
    model = PreviewModel()
    sent = []
    model.useRequested.connect(sent.append)

    model.use("   ")
    assert sent == []


def test_use_refreshes_token_stats(qapp):
    """编辑后 token 统计跟着变，状态栏不与框内内容脱节。"""
    model = PreviewModel()
    model.begin("A")
    model.set_result(EnhancedPrompt(original_prompt="A", enhanced_prompt="B"))
    before = model.tokenStats["enhanced"]

    model.use("这是一段被用户改写得长很多的增强结果文本")

    assert model.tokenStats["enhanced"] > before
    assert model.tokenStats["total"] == (
        model.tokenStats["original"]
        + model.tokenStats["context"]
        + model.tokenStats["enhanced"]
    )
