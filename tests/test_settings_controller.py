"""设置页控制层单测（不触碰用户真实配置目录）。

SettingsController 承接了原 QWidget 设置窗里与列表相关的逻辑：模型配置 CRUD、
单一生效、API Key 掩码语义，以及项目索引增删与异步建索引。构造时把 HOME 指到 tmp_path，避免 SettingsModel
读写用户真实的 ~/.context-pilot/config.toml。
"""

import time

import pytest
from PySide6.QtCore import QCoreApplication, QThread

from context_pilot.ui.settings_controller import SettingsController
from context_pilot.ui.settings_model import SettingsModel


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """把「用户目录」重定向到临时目录（Windows 读 USERPROFILE，POSIX 读 HOME）。"""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def ctl(qapp, isolated_home, tmp_path):
    controller = SettingsController(SettingsModel(), base_dir=tmp_path / "data")
    yield controller
    controller.shutdown()


# ---------- 模型配置 ----------
def test_add_profile_masks_api_key(ctl):
    assert ctl.addProfile("OpenAI 主力", "https://api.openai.com/v1", "sk-secret-key-9012", "gpt-4o-mini")

    profiles = ctl.profiles
    assert len(profiles) == 1
    assert profiles[0]["name"] == "OpenAI 主力"
    assert profiles[0]["model"] == "gpt-4o-mini"
    assert profiles[0]["enabled"] is False
    # 掩码：前 4 后 4，中间打星；明文不得出现在列表数据里
    assert profiles[0]["apiKey"] == "sk-s****9012"
    assert ctl.messageError is False


def test_add_profile_rejects_missing_fields(ctl):
    assert ctl.addProfile("", "https://api.openai.com/v1", "sk-xxx", "gpt-4o-mini") is False
    assert ctl.messageError is True
    assert ctl.profiles == []


def test_update_profile_without_key_edit_keeps_secret(ctl):
    ctl.addProfile("cfg", "https://api.openai.com/v1", "sk-secret-key-9012", "gpt-4o")
    pid = ctl.profiles[0]["id"]

    # 未编辑过 key（传掩码值 + key_edited=False）时明文必须保持原样
    assert ctl.updateProfile(pid, "cfg2", "https://api.openai.com/v2", "gpt-4o-mini",
                             ctl.profiles[0]["apiKey"], False)
    assert ctl.revealKey(pid) == "sk-secret-key-9012"
    assert ctl.profiles[0]["name"] == "cfg2"
    assert ctl.profiles[0]["baseUrl"] == "https://api.openai.com/v2"


def test_update_profile_with_key_edit_replaces_secret(ctl):
    ctl.addProfile("cfg", "https://api.openai.com/v1", "sk-secret-key-9012", "gpt-4o")
    pid = ctl.profiles[0]["id"]

    assert ctl.updateProfile(pid, "cfg", "https://api.openai.com/v1", "gpt-4o",
                             "sk-brand-new-key-3456", True)
    assert ctl.revealKey(pid) == "sk-brand-new-key-3456"


def test_multiple_profiles_can_be_enabled(ctl):
    """生效是多选：两条都能同时生效，互不取消。"""
    ctl.addProfile("a", "https://api.a.com/v1", "sk-aaaa", "ma")
    ctl.addProfile("b", "https://api.b.com/v1", "sk-bbbb", "mb")
    first, second = ctl.profiles[0]["id"], ctl.profiles[1]["id"]

    ctl.setProfileEnabled(first, True)
    ctl.setProfileEnabled(second, True)

    states = {p["id"]: p["enabled"] for p in ctl.profiles}
    assert states[first] is True
    assert states[second] is True

    # 取消其中一条只影响自己
    ctl.setProfileEnabled(first, False)
    states = {p["id"]: p["enabled"] for p in ctl.profiles}
    assert states[first] is False
    assert states[second] is True


def test_delete_profile(ctl):
    ctl.addProfile("a", "https://api.a.com/v1", "sk-aaaa", "ma")
    ctl.deleteProfile(ctl.profiles[0]["id"])
    assert ctl.profiles == []


# ---------- 项目索引 ----------
def test_add_project_validates_path(ctl, tmp_path):
    existing = tmp_path / "project"
    existing.mkdir()

    assert ctl.addProject(str(existing)) is True
    assert ctl.projects[0]["name"] == "project"
    assert ctl.projects[0]["status"] == "pending"

    assert ctl.addProject("") is False
    assert ctl.addProject(str(tmp_path / "nope")) is False
    assert len(ctl.projects) == 1


def test_build_index_updates_status(qapp, ctl, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('hi')", encoding="utf-8")
    ctl.addProject(str(project))
    assert ctl.projects[0]["status"] == "pending"

    ctl.buildIndex(ctl.projects[0]["id"])
    assert ctl.projects[0]["status"] == "running"

    deadline = time.time() + 5
    while time.time() < deadline and ctl.projects[0]["status"] == "running":
        QCoreApplication.processEvents()
        time.sleep(0.02)
    assert ctl.projects[0]["status"] == "done"
    assert ctl.messageError is False


# ---------- 风格预设 ----------
def test_styles_seeded_with_builtins(ctl):
    """首次访问自动写入内置四档优化模式。"""
    keys = [s["id"] for s in ctl.styles]
    assert keys == ["default", "basic", "professional", "planning"]
    assert all(s["builtin"] for s in ctl.styles)
    # 每档都带 mode 与 description
    modes = {s["id"]: s["mode"] for s in ctl.styles}
    assert modes["default"] == "task"
    assert modes["basic"] == "basic"
    assert modes["professional"] == "professional"
    assert modes["planning"] == "planning"


def test_add_update_delete_style(ctl):
    assert ctl.addStyle("精炼要点", "只输出结论", 300)
    styles = ctl.styles
    custom = [s for s in styles if s["label"] == "精炼要点"]
    assert len(custom) == 1
    assert custom[0]["maxTokens"] == 300
    assert custom[0]["builtin"] is False

    key = custom[0]["id"]
    assert ctl.updateStyle(key, "精炼要点2", "只输出结论2", 400)
    updated = [s for s in ctl.styles if s["id"] == key][0]
    assert updated["label"] == "精炼要点2"
    assert updated["maxTokens"] == 400

    ctl.deleteStyle(key)
    assert all(s["id"] != key for s in ctl.styles)


def test_add_style_rejects_empty_label(ctl):
    assert ctl.addStyle("  ", "指令", 300) is False
    assert ctl.messageError is True
