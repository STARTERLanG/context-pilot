"""配置读写单测。全部隔离到 tmp_path，不触碰用户家目录。"""

from pathlib import Path

from context_pilot.config import (
    BehaviorConfig,
    Config,
    GeneralConfig,
    LlmConfig,
    config_path,
    load,
    save,
    with_updates,
)


def test_load_creates_default_file_on_first_run(tmp_path):
    config = load(base_dir=tmp_path)

    assert config_path(tmp_path).exists()
    assert config.llm.provider == "stub"  # 默认不联网
    assert config.general.hotkey == "ctrl+shift+e"
    assert config.memory.enabled is True


def test_save_then_load_roundtrip(tmp_path):
    original = Config(
        general=GeneralConfig(project_root="D:/work/app", hotkey="ctrl+alt+p"),
        llm=LlmConfig(provider="openai", api_key="sk-x", model="deepseek-chat"),
        behavior=BehaviorConfig(autostart=True, auto_copy=False),
    )

    save(original, base_dir=tmp_path)
    reloaded = load(base_dir=tmp_path)

    assert reloaded.general.project_root == "D:/work/app"
    assert reloaded.general.hotkey == "ctrl+alt+p"
    assert reloaded.llm.provider == "openai"
    assert reloaded.llm.api_key == "sk-x"
    assert reloaded.behavior.autostart is True
    assert reloaded.behavior.auto_copy is False


def test_save_escapes_windows_path(tmp_path):
    """Windows 反斜杠路径写回后仍能解析，不会破坏 TOML 结构。"""
    config = with_updates(
        Config(), general=GeneralConfig(project_root=r"D:\work\app", hotkey="ctrl+shift+e")
    )

    save(config, base_dir=tmp_path)
    reloaded = load(base_dir=tmp_path)

    assert reloaded.general.project_root == r"D:\work\app"


def test_save_escapes_quotes_in_api_key(tmp_path):
    config = with_updates(Config(), llm=LlmConfig(api_key='sk-"quote"'))
    save(config, base_dir=tmp_path)
    assert load(base_dir=tmp_path).llm.api_key == 'sk-"quote"'


def test_with_updates_replaces_only_target_section():
    original = Config()
    updated = with_updates(original, llm=LlmConfig(provider="openai"))

    assert updated.llm.provider == "openai"
    assert updated.general.hotkey == original.general.hotkey  # 其他 section 不变


def test_load_partial_file_falls_back_to_defaults(tmp_path):
    Path(tmp_path, "config.toml").write_text("[llm]\nmodel = 'x'\n", encoding="utf-8")

    config = load(base_dir=tmp_path)

    assert config.llm.model == "x"
    assert config.llm.provider == "stub"  # 缺失字段回落到默认
    assert config.context.max_tokens == 6000
