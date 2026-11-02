"""后台任务线程：增强调用与远端模型列表拉取。

放在同一处的理由：两者都是「主线程不得阻塞」的网络/耗时操作，封装方式一致，
不阻塞 GUI 是热键与托盘保持响应的前提。
"""

import asyncio

from PySide6.QtCore import QThread, Signal

from context_pilot.core.logging_setup import get_logger
from context_pilot.core.models import EnhanceOptions
from context_pilot.core.pipeline import Pipeline


class EnhanceWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        pipeline: Pipeline,
        prompt: str,
        options: EnhanceOptions | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._prompt = prompt
        self._options = options

    def run(self) -> None:
        try:
            result = asyncio.run(self._pipeline.enhance(self._prompt, self._options))
        except Exception as exc:  # UI 边界：任何异常都转成失败信号展示给用户，不静默
            # 状态栏只能放一句话，完整堆栈进日志——网络超时、端点 401、
            # 检索器抛错都靠这里留下现场（PRD 三十六章）。
            get_logger(__name__).exception(
                "增强失败：%s | 指令=%s", exc, self._prompt[:80]
            )
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)


class ModelsFetchThread(QThread):
    """拉取 OpenAI 兼容端点的模型列表（GET /v1/models）。

    设置页获取可用模型、主页面丰富「模型」下拉都用它；无论成败都要emit，
    以便调用方退出「加载中」状态。
    """

    modelsReady = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        base_url: str,
        api_key: str,
        parent=None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._api_key = api_key
        # None 时沿用 fetch_models 的默认超时（MODELS_FETCH_TIMEOUT）
        self._timeout = timeout

    def run(self) -> None:
        from context_pilot.optimizer.openai_provider import fetch_models

        try:
            if self._timeout is None:
                models = fetch_models(self._base_url, self._api_key)
            else:
                models = fetch_models(self._base_url, self._api_key, timeout=self._timeout)
        except Exception as exc:  # 异常不得冒泡到事件循环
            # 只记端点不记密钥：api_key 由脱敏兜底，这里索性不传
            get_logger(__name__).warning("拉取模型列表失败：%s | 端点=%s", exc, self._base_url)
            self.failed.emit(str(exc))
            return
        self.modelsReady.emit(list(models))
