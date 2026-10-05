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
