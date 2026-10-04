"""配置读写单测。全部隔离到 tmp_path，不触碰用户家目录。"""

from context_pilot.config import config_path, load


def test_load_creates_default_file_on_first_run(tmp_path):
    config = load(base_dir=tmp_path)

    assert config_path(tmp_path).exists()
    assert config.llm.provider == "stub"  # 默认不联网
    assert config.memory.enabled is True


def test_load_reads_custom_values(tmp_path):
    (tmp_path / "config.toml").write_text(
        """
[general]
project_root = "D:/work/app"

[llm]
provider = "openai"
base_url = "https://api.deepseek.com/v1"
api_key = "sk-test"
model = "deepseek-chat"
timeout = 30

[memory]
enabled = false

[context]
max_tokens = 8000
""",
        encoding="utf-8",
    )

    config = load(base_dir=tmp_path)

    assert config.general.project_root == "D:/work/app"
    assert config.llm.provider == "openai"
    assert config.llm.base_url == "https://api.deepseek.com/v1"
    assert config.llm.timeout == 30.0
    assert config.memory.enabled is False
    assert config.context.max_tokens == 8000


def test_load_partial_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.toml").write_text("[llm]\nmodel = 'x'\n", encoding="utf-8")

    config = load(base_dir=tmp_path)

    assert config.llm.model == "x"
    assert config.llm.provider == "stub"  # 缺失字段回落到默认
