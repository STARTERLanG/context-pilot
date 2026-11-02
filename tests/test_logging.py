"""日志模块单测：脱敏、幂等、文件不可用时的降级。"""

import logging

import pytest

from context_pilot.core import logging_setup
from context_pilot.core.logging_setup import get_logger, log_dir, redact, setup_logging


@pytest.fixture(autouse=True)
def _isolate():
    """每个用例前重置 logger 状态，避免 handler 在用例间串味。"""
    logger = logging.getLogger("context_pilot")
    saved_handlers = logger.handlers[:]
    saved_level = logger.level
    saved_configured = getattr(logger, "_context_pilot_configured", False)
    yield
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    for handler in saved_handlers:
        logger.addHandler(handler)
    logger.setLevel(saved_level)
    logger._context_pilot_configured = saved_configured  # type: ignore[attr-defined]


# ── 脱敏 ──────────────────────────────────────────────────────────────


def test_redact_masks_openai_key():
    assert "sk-***" in redact("key = sk-abcdefgh12345678")
    assert "abcdefgh12345678" not in redact("key = sk-abcdefgh12345678")


def test_redact_masks_project_scoped_key():
    masked = redact("Authorization: Bearer sk-proj-AbCdEfGhIjKlMnOp")
    assert "AbCdEfGhIjKlMnOp" not in masked
    assert "***" in masked


def test_redact_masks_key_value_pairs():
    for raw in (
        "api_key=SECRETVALUE123",
        "api_key: SECRETVALUE123",
        '"api_key": "SECRETVALUE123"',
        "token=abc123xyz",
        "password: hunter2",
    ):
        masked = redact(raw)
        assert "SECRETVALUE123" not in masked
        assert "hunter2" not in masked
        assert "***" in masked


def test_redact_keeps_ordinary_text():
    """不能误伤正常内容：代码里的变量名、文件路径都不该被改写。"""
    raw = "读取 src/order/service.py 时超时，token_cost=0"
    # token 后紧跟 = 会被脱敏（保守策略），但其余部分必须原样保留
    assert "src/order/service.py" in redact(raw)
    assert "超时" in redact(raw)


def test_logger_output_is_redacted(tmp_path):
    """经过 logger 的记录同样脱敏——验证的是 Filter 生效，而非只有 redact 函数能用。

    直接读日志文件而非 caplog：context_pilot 的 logger 设了 propagate=False
    （避免第三方库噪音），caplog 挂在 root 上收不到，落盘才是真实路径。
    """
    path = setup_logging(base_dir=tmp_path, to_stderr=False)
    get_logger("test.redact").info("请求失败 api_key=PLAINTEXTKEY123")

    text = path.read_text(encoding="utf-8")  # RotatingFileHandler.emit 自带 flush
    assert "PLAINTEXTKEY123" not in text
    assert "***" in text


# ── 初始化行为 ────────────────────────────────────────────────────────


def test_setup_is_idempotent(tmp_path):
    """重复调用不叠加 handler，否则每条日志会被写 N 遍。"""
    first = setup_logging(base_dir=tmp_path, to_stderr=False)
    count = len(logging.getLogger("context_pilot").handlers)
    second = setup_logging(base_dir=tmp_path, to_stderr=False)

    assert len(logging.getLogger("context_pilot").handlers) == count
    assert first == second


def test_setup_writes_log_file(tmp_path):
    path = setup_logging(base_dir=tmp_path, to_stderr=False)
    assert path is not None
    assert path.exists()

    get_logger("test.file").info("一行测试日志")
    # 不用 logging.shutdown()：那会关闭全局所有 handler，影响后续用例
    assert "一行测试日志" in path.read_text(encoding="utf-8")


def test_setup_degrades_when_dir_unusable(tmp_path, caplog):
    """目录不可写时降级为 stderr，绝不因此崩溃（日志不是功能）。"""
    blocker = tmp_path / "iam_a_file"
    blocker.write_text("x", encoding="utf-8")  # 用它当父目录必然失败

    with caplog.at_level(logging.WARNING, logger="context_pilot"):
        path = setup_logging(base_dir=blocker, to_stderr=False)

    assert path is None
    assert "日志文件不可用" in caplog.text


def test_get_logger_namespaced():
    assert get_logger("a.b").name == "context_pilot.a.b"
    # 已在命名空间下时不重复加前缀
    assert get_logger("context_pilot.a").name == "context_pilot.a"


def test_log_dir_default_under_home():
    assert log_dir().name == "logs"
    assert log_dir().parent.name == ".context-pilot"


def test_module_exposes_expected_api():
    """防止重构时把入口弄丢：这些是 app.py 依赖的符号。"""
    for name in ("setup_logging", "get_logger", "redact", "log_dir"):
        assert hasattr(logging_setup, name)
