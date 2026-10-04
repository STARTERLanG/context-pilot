"""应用装配与入口：QApplication → 单实例 → 托盘/热键/窗口 → 事件循环。"""

import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from context_pilot.core.pipeline import Pipeline
from context_pilot.platform.clipboard import read_clipboard_text, write_clipboard_text
from context_pilot.platform.hotkey import GlobalHotkey, HotkeyRegistrationError
from context_pilot.platform.single_instance import SingleInstance
from context_pilot.ui.preview_model import PreviewModel
from context_pilot.ui.preview_window import PreviewWindow
from context_pilot.ui.tray import Tray
from context_pilot.ui.worker import EnhanceWorker


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ContextPilot")
    # 关掉预览窗只是隐藏，进程继续驻留托盘
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("系统托盘不可用，ContextPilot 无法运行", file=sys.stderr)
        return 1

    # 先建 QApplication 再判单实例（QLocalServer 需要事件循环）
    instance = SingleInstance()
    if not instance.try_acquire():
        return 0

    pipeline = Pipeline()
    model = PreviewModel()
    window = PreviewWindow(model)
    tray = Tray()
    hotkey = GlobalHotkey()

    # QThread 被 GC 会崩，需持有引用
    running_workers: list[EnhanceWorker] = []

    def on_enhance() -> None:
        prompt = read_clipboard_text()
        model.begin(prompt)
        window.show_and_activate()
        if not prompt.strip():
            model.set_failed("剪贴板为空")
            return

        worker = EnhanceWorker(pipeline, prompt)
        worker.succeeded.connect(model.set_result)
        worker.failed.connect(model.set_failed)
        worker.finished.connect(lambda: running_workers.remove(worker))
        running_workers.append(worker)
        worker.start()

    def on_use(text: str) -> None:
        write_clipboard_text(text)
        window.hide()

    def on_quit() -> None:
        hotkey.unregister()
        app.quit()

    try:
        hotkey.register()
    except HotkeyRegistrationError as exc:
        tray.notify("ContextPilot 热键不可用", str(exc))

    hotkey.pressed.connect(on_enhance)
    model.useRequested.connect(on_use)
    model.closeRequested.connect(window.hide)
    tray.showRequested.connect(on_enhance)
    tray.quitRequested.connect(on_quit)
    instance.show_requested.connect(on_enhance)

    app.aboutToQuit.connect(hotkey.unregister)
    tray.show()
    return app.exec()
