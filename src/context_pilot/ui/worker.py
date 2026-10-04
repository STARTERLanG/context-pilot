"""把增强任务放到工作线程，避免阻塞 GUI 主线程（热键与托盘必须保持响应）。"""

import asyncio

from PySide6.QtCore import QThread, Signal

from context_pilot.core.pipeline import Pipeline


class EnhanceWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, pipeline: Pipeline, prompt: str, parent=None) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._prompt = prompt

    def run(self) -> None:
        try:
            result = asyncio.run(self._pipeline.enhance(self._prompt))
        except Exception as exc:  # UI 边界：任何异常都转成失败信号展示给用户，不静默
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)
