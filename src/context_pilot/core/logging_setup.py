"""本地日志（PRD 第三十六章）。

设计取舍：

- **只挂 context_pilot 这一个 logger**，不改 root。第三方库（ requests /
  PySide6 ）的噪音不该进我们的日志文件；真要看它们的调试信息可以手动改级别。
- **文件写入失败不致命**。日志是排查手段，不是功能：目录不可写、磁盘满、
  被安全策略拦下时一律降级为 stderr 输出，绝不让启动失败。
- **默认脱敏**。异常里经常夹带 api_key / token，直接落盘等于把凭据写进明文
  文件，所以所有经过本模块的记录都先过一遍正则替换。
"""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "context_pilot"
_LOG_FILE = "context-pilot.log"
_MAX_BYTES = 1_000_000  # 单文件 1 MB
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 脱敏规则：命中即整段替换为占位符，避免凭据以明文落盘。
# 每条都是 (正则, 替换)，按列表顺序依次应用。
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # OpenAI / 兼容端点的 sk-xxx（含项目键 sk-proj-xxx）
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    # Authorization 头与 Bearer token
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***"),
    # 各类 key=value / key: value 形式（api_key、token、password、secret…）。
    # 第二组吞掉 JSON 写法里键名后的闭合引号：`"api_key": "xxx"`。
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token"
            r"|password|passwd|secret|authorization)\b([\"']?)(\s*[=:]\s*)"
            r"(\"[^\"]*\"|'[^']*'|[^\s,;)}\]]+)"
        ),
        r"\1\2\3***",
    ),
)


def redact(text: str) -> str:
    """把文本里的凭据片段替换为 ***。幂等，可安全重复调用。"""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class _RedactingFilter(logging.Filter):
    """在记录落盘前脱敏。放在 Filter 而非 Formatter 上：Formatter 只处理
    最终字符串，而 Filter 能同时覆盖消息与参数，且不干扰格式本身。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(str(record.msg))
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact(str(v)) for k, v in record.args.items()}
                else:
                    record.args = tuple(redact(str(a)) for a in record.args)
        except Exception:  # 脱敏本身出错也不能丢日志
            pass
        return True


def log_dir(base_dir: Path | None = None) -> Path:
    """日志文件所在目录。默认 ~/.context-pilot/logs。"""
    return (base_dir or Path.home() / ".context-pilot") / "logs"


def setup_logging(
    base_dir: Path | None = None,
    level: int | str = logging.INFO,
    to_stderr: bool = True,
) -> Path | None:
    """初始化日志。返回日志文件路径；文件不可用时返回 None（已降级到 stderr）。

    幂等：重复调用只更新级别，不会叠加 handler。这点对测试与热重载很重要。
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False  # 不向 root 冒泡，避免重复输出

    # 已初始化过：只刷新级别即可
    if getattr(logger, "_context_pilot_configured", False):
        for handler in logger.handlers:
            handler.setLevel(level)
        return getattr(logger, "_context_pilot_logfile", None)

    redacting = _RedactingFilter()
    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    if to_stderr:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        stream.addFilter(redacting)
        logger.addHandler(stream)

    logfile: Path | None = None
    try:
        directory = log_dir(base_dir)
        directory.mkdir(parents=True, exist_ok=True)
        logfile = directory / _LOG_FILE
        file_handler = RotatingFileHandler(
            logfile,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redacting)
        logger.addHandler(file_handler)
    except OSError as exc:  # 目录不可写 / 被策略拦截：降级，不阻断启动
        logger.warning("日志文件不可用，仅输出到 stderr：%s", exc)
        logfile = None

    logger._context_pilot_configured = True  # type: ignore[attr-defined]
    logger._context_pilot_logfile = logfile  # type: ignore[attr-defined]
    return logfile


def get_logger(name: str) -> logging.Logger:
    """取 context_pilot 命名空间下的 logger。

    传 `__name__` 即可：模块名会被规整到该命名空间下，未初始化时也不会报错
    （只是没有 handler，静默丢弃）。
    """
    if name.startswith(_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
