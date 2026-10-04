"""Agent 适配器单测。"""

from context_pilot.adapters.base import AgentAdapter
from context_pilot.adapters.clipboard import claude, codex, gemini


def test_clipboard_adapter_writes_text(monkeypatch):
    captured = []

    def fake_write(text):
        captured.append(text)

    # patch 适配器模块里 import 的名字，而非平台模块本身
    monkeypatch.setattr("context_pilot.adapters.clipboard.write_clipboard_text", fake_write)

    adapter = claude()
    adapter.deliver("## Objective\n\n修复")

    assert captured == ["## Objective\n\n修复"]
    assert adapter.name == "claude"


def test_all_adapters_satisfy_protocol():
    for adapter in (claude(), codex(), gemini()):
        assert isinstance(adapter, AgentAdapter)


def test_adapter_names():
    assert claude().name == "claude"
    assert codex().name == "codex"
    assert gemini().name == "gemini"
