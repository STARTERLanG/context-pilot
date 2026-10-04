"""应用装配与入口：QApplication → 单实例 → 托盘/热键/窗口 → 事件循环。

这里也是唯一把配置、提供方与检索器装配起来的地方；引擎模块彼此不感知。
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from context_pilot.config import Config, load as load_config
from context_pilot.core.pipeline import Pipeline
from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore
from context_pilot.optimizer.openai_provider import OpenAiProvider
from context_pilot.optimizer.provider import LlmProvider, StubProvider
from context_pilot.platform.clipboard import read_clipboard_text, write_clipboard_text
from context_pilot.platform.hotkey import GlobalHotkey, HotkeyRegistrationError
from context_pilot.platform.single_instance import SingleInstance
from context_pilot.retrieval.base import Retriever
from context_pilot.retrieval.keyword import KeywordRetriever
from context_pilot.ui.preview_model import PreviewModel
from context_pilot.ui.preview_window import PreviewWindow
from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.settings_window import SettingsWindow
from context_pilot.ui.tray import Tray
from context_pilot.ui.worker import EnhanceWorker


def _handle_close(state: dict, app: QApplication) -> None:
    """按配置决定关窗行为：最小化到托盘或退出。"""
    if state["config"].behavior.close_to_tray:
        for widget in app.topLevelWindows():
            widget.hide()
    else:
        app.quit()


def _build_provider(config: Config) -> LlmProvider:
    if config.llm.provider == "openai":
        return OpenAiProvider(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            model=config.llm.model,
            timeout=config.llm.timeout,
        )
    # 默认 stub：离线可跑，用于验证链路
    return StubProvider()


def _build_retrievers(config: Config, project_root: Path) -> list[Retriever]:
    retrievers: list[Retriever] = [KeywordRetriever()]
    if config.memory.enabled:
        try:
            retrievers.append(MemoryRetriever(MemoryStore(project_root)))
        except OSError:
            # 记忆库不可用不应阻断主流程
            pass
    return retrievers


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

    config = load_config()
    project_root = (
        Path(config.general.project_root) if config.general.project_root else Path.cwd()
    )
    # 用可变容器承载，设置保存后需要原地替换
    state = {
        "config": config,
        "pipeline": Pipeline(
            project_root=project_root,
            provider=_build_provider(config),
            retrievers=_build_retrievers(config, project_root),
        ),
    }
    model = PreviewModel()
    window = PreviewWindow(model, on_close=lambda: _handle_close(state, app))
    tray = Tray()
    hotkey = GlobalHotkey(config.general.hotkey)
    settings_model = SettingsModel(project_root)
    settings_window = SettingsWindow(settings_model)

    # QThread 被 GC 会崩，需持有引用
    running_workers: list[EnhanceWorker] = []

    def on_enhance() -> None:
        prompt = read_clipboard_text()
        model.begin(prompt)
        window.show_and_activate()
        if not prompt.strip():
            model.set_failed("剪贴板为空")
            return

        worker = EnhanceWorker(state["pipeline"], prompt)
        worker.succeeded.connect(model.set_result)
        worker.failed.connect(model.set_failed)
        worker.finished.connect(lambda: running_workers.remove(worker))
        running_workers.append(worker)
        worker.start()

    def on_use(text: str) -> None:
        if state["config"].behavior.auto_copy:
            write_clipboard_text(text)
        window.hide()

    def on_settings() -> None:
        settings_model.reloadMemories()
        settings_window.show_and_activate()

    def on_saved() -> None:
        # 保存后重建：配置可能改了 project_root / provider / 热键
        new_config = load_config()
        state["config"] = new_config
        root = (
            Path(new_config.general.project_root)
            if new_config.general.project_root
            else Path.cwd()
        )
        state["pipeline"] = Pipeline(
            project_root=root,
            provider=_build_provider(new_config),
            retrievers=_build_retrievers(new_config, root),
        )
        try:
            hotkey.rebind(new_config.general.hotkey)
        except HotkeyRegistrationError as exc:
            tray.notify("热键未能应用", str(exc))

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
    tray.settingsRequested.connect(on_settings)
    tray.quitRequested.connect(on_quit)
    settings_model.saved.connect(on_saved)
    settings_model.saveFailed.connect(
        lambda msg: tray.notify("设置未保存", msg)
    )
    instance.show_requested.connect(on_enhance)

    app.aboutToQuit.connect(hotkey.unregister)
    tray.show()

    # 配置了真实提供方却缺 Key 时立即提示，而不是等用户按热键才失败
    if config.llm.provider == "openai" and not config.llm.api_key:
        tray.notify(
            "ContextPilot 未配置 API Key",
            "请编辑 ~/.context-pilot/config.toml 填写 llm.api_key",
        )

    return app.exec()
