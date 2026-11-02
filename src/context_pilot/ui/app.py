"""应用装配与入口：QApplication → 单实例 → 托盘/热键/窗口 → 事件循环。

这里也是唯一把配置、提供方与检索器装配起来的地方；引擎模块彼此不感知。
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from context_pilot.adapters.base import AgentAdapter
from context_pilot.adapters.clipboard import claude, codex, gemini
from context_pilot.config import Config, load as load_config
from context_pilot.core.logging_setup import get_logger, setup_logging
from context_pilot.core.models import EnhanceOptions
from context_pilot.core.pipeline import Pipeline
from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore
from context_pilot.optimizer.openai_provider import OpenAiProvider
from context_pilot.optimizer.provider import LlmProvider
from context_pilot.platform.clipboard import read_clipboard_text, write_clipboard_text
from context_pilot.platform.hotkey import GlobalHotkey, HotkeyRegistrationError
from context_pilot.platform.single_instance import SingleInstance
from context_pilot.retrieval.base import Retriever
from context_pilot.ui.icon import app_icon
from context_pilot.ui.preview_model import PreviewModel
from context_pilot.ui.preview_window import PreviewWindow
from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.session_controller import SessionController
from context_pilot.ui.tray import Tray
from context_pilot.ui.worker import EnhanceWorker


def _handle_close(state: dict, app: QApplication) -> None:
    """按配置决定关窗行为：最小化到托盘或退出。"""
    if state["config"].behavior.close_to_tray:
        for widget in app.topLevelWindows():
            widget.hide()
    else:
        app.quit()


def _build_provider(config: Config, target: dict | None = None) -> LlmProvider:
    """按主页面选中的增强目标构建 Provider。

    target 来自 session_ctl.provider_target()：用户明确选定的那一条已生效配置。
    没有可用目标时**不猜**，也绝不回落到离线桩——桩只会把原文抄回来，
    看起来像「模型没效果」，比直接报错更难排查。此时返回无参 Provider，
    调用时由它抛出「未配置可用的增强目标」。
    """
    if target and target.get("api_key") and target.get("model"):
        return OpenAiProvider(
            base_url=target["base_url"],
            api_key=target["api_key"],
            model=target["model"],
            timeout=config.llm.timeout,
            temperature=target.get("temperature", 1.0),
        )
    return OpenAiProvider(timeout=config.llm.timeout)


def _build_retrievers(config: Config, project_root: Path) -> list[Retriever]:
    """构造「默认代码检索之外」的附加检索器（当前只有记忆）。

    返回值经 Pipeline 的 extra_retrievers **追加**在默认三级检索之后，
    不再像从前那样顶替掉 ripgrep/AST/向量——后者要让「装了记忆就没有代码
    检索」的问题不再复发。
    """
    retrievers: list[Retriever] = []
    if config.memory.enabled:
        try:
            retrievers.append(MemoryRetriever(MemoryStore(project_root)))
        except OSError:
            # 记忆库不可用不应阻断主流程
            pass
    return retrievers


def _build_adapter(config: Config) -> AgentAdapter:
    agents = {"claude": claude, "codex": codex, "gemini": gemini}
    return agents.get(config.general.agent, claude)()


def main() -> int:
    # 尽早初始化日志：此后的装配、检索、增强失败都能留下现场（PRD 三十六章）。
    # 文件不可用时自动降级到 stderr，不会因此启动失败。
    setup_logging()
    log = get_logger(__name__)

    app = QApplication(sys.argv)
    app.setApplicationName("ContextPilot")
    # 全局窗口图标：任务栏 / Alt-Tab / 设置窗标题栏共用
    app.setWindowIcon(app_icon())
    # 关掉预览窗只是隐藏，进程继续驻留托盘
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.error("系统托盘不可用，无法启动")
        print("系统托盘不可用，ContextPilot 无法运行", file=sys.stderr)
        return 1

    # 先建 QApplication 再判单实例（QLocalServer 需要事件循环）
    instance = SingleInstance()
    if not instance.try_acquire():
        log.info("已有实例在运行，本次退出")
        return 0

    try:
        config = load_config()
    except Exception:
        # 配置损坏（手改坏 toml、编码错误）不应让应用打不开：退回默认值并记下原因
        log.exception("配置加载失败，回退默认配置")
        config = Config()
    # 用可变容器承载，设置保存后需要原地替换；pipeline 由下面的 rebuild 建立
    state = {"config": config, "pipeline": None, "adapter": _build_adapter(config)}
    model = PreviewModel()
    model.set_adapter(state["adapter"])
    settings_model = SettingsModel()
    # 主页面「项目 / 模型」选择：项目只活在会话内存里，增强目标跨启动保留
    session_ctl = SessionController(config)
    window = PreviewWindow(
        model,
        settings=settings_model,
        session=session_ctl,
        on_close=lambda: _handle_close(state, app),
    )
    tray = Tray()
    # 两个热键需不同 id：RegisterHotKey 以 id 区分同一进程内的多个注册
    hotkey = GlobalHotkey(config.general.hotkey, hotkey_id=1)
    toggle_hotkey = GlobalHotkey(config.general.toggle_hotkey, hotkey_id=2)

    # QThread 被 GC 会崩，需持有引用
    running_workers: list[EnhanceWorker] = []

    def rebuild_pipeline() -> None:
        """按当前「项目 / 模型」选择重建管线：下一次增强立即按新选择执行。

        扫描失败时不替换旧管线——界面应该还能用上一次可用的配置继续工作，
        失败原因走底部状态栏告知。
        """
        cfg = state["config"]
        # 「无项目」时 current_project_root 为空串，project_root 传 None：
        # Pipeline 据此跳过仓库扫描与检索器构建（仅保留 provider）。
        root_str = session_ctl.current_project_root
        root = Path(root_str) if root_str else None
        try:
            state["pipeline"] = Pipeline(
                project_root=root,
                provider=_build_provider(cfg, session_ctl.provider_target()),
                extra_retrievers=_build_retrievers(cfg, root) if root is not None else [],
                styles=session_ctl.style_objects(),
                # 用户在设置页改的 token 预算终于能真正影响增强了
                budget=cfg.context.as_budget(),
            )
        except Exception as exc:  # UI 边界：扫描/配置异常转为状态栏文案
            # 完整堆栈进日志：状态栏只放得下一句话，排查要靠这里的现场
            log.exception("管线重建失败：%s", exc)
            model.set_failed(f"切换项目失败：{exc}")

    # 首次装配：以当前配置对应的项目与模型建立管线
    rebuild_pipeline()

    def on_enhance() -> None:
        # 只把剪贴板内容载入输入框，不再自动增强——增强改由用户点「增强」按钮触发
        prompt = read_clipboard_text()
        model.load(prompt)
        # 增强结果属于主页面：即便当前停在设置页也要切回去再看结果
        window.show_main_page()
        window.show_and_activate()
        if not prompt.strip():
            model.set_failed("剪贴板为空")

    def on_enhance_requested(text: str) -> None:
        # 「无项目」时不检索项目代码：仅优化原始表述（include_context=False）
        # 输出风格与长度上限取自顶行「风格」下拉选中项（会话级，不落盘）。
        style = session_ctl.current_style
        style_obj = session_ctl.style_store.get(style)
        max_tokens = style_obj.max_tokens if style_obj else 6000
        options = EnhanceOptions(
            include_context=session_ctl.has_project,
            style=style,
            max_tokens=max_tokens,
        )
        worker = EnhanceWorker(state["pipeline"], text, options=options)
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
        """打开设置：弹出主窗口并切到设置页（不再是独立窗口）。"""
        window.show_and_activate()
        window.open_settings()

    def on_toggle_window() -> None:
        """切换界面：已显示则关闭（隐藏），未显示则弹出并激活。"""
        window.toggle()

    def rebind_hotkeys(new_config: Config) -> None:
        """保存后重绑两个热键；被占用或非法时各自单独提示，互不影响。"""
        for target, sequence, title in (
            (hotkey, new_config.general.hotkey, "增强热键未能应用"),
            (toggle_hotkey, new_config.general.toggle_hotkey, "界面开关热键未能应用"),
        ):
            try:
                target.rebind(sequence)
            except HotkeyRegistrationError as exc:
                log.warning("热键绑定失败（%s）：%s", sequence, exc)
                tray.notify(title, str(exc))

    def on_saved() -> None:
        # 保存后重建：配置可能改了 project_root / provider / 热键
        try:
            new_config = load_config()
        except Exception:
            log.exception("设置保存后重新加载配置失败，沿用内存中的配置")
            return
        state["config"] = new_config
        # 默认模型可能随配置改变，重读候选列表（已选中的若还在则保留）
        session_ctl.set_config(new_config)
        state["adapter"] = _build_adapter(new_config)
        model.set_adapter(state["adapter"])
        rebind_hotkeys(new_config)
        rebuild_pipeline()

    def on_quit() -> None:
        hotkey.unregister()
        toggle_hotkey.unregister()
        app.quit()

    try:
        hotkey.register()
    except HotkeyRegistrationError as exc:
        tray.notify("ContextPilot 热键不可用", str(exc))
    try:
        toggle_hotkey.register()
    except HotkeyRegistrationError as exc:
        tray.notify("界面开关热键不可用", str(exc))

    hotkey.pressed.connect(on_enhance)
    toggle_hotkey.pressed.connect(on_toggle_window)
    model.useRequested.connect(on_use)
    model.enhanceRequested.connect(on_enhance_requested)
    model.closeRequested.connect(window.hide)
    tray.showRequested.connect(on_enhance)
    tray.settingsRequested.connect(on_settings)
    tray.quitRequested.connect(on_quit)
    settings_model.saved.connect(on_saved)
    # 保存失败（热键重复 / 预算超额 / 落盘异常）：显示页内保存栏即可，不必打扰托盘
    settings_model.saveFailed.connect(
        lambda msg: window.settings_ctl.notify(msg, error=True)
    )
    instance.show_requested.connect(on_enhance)
    # 顶行「项目 / 模型」切换：立即按新选择重建管线
    session_ctl.selectionChanged.connect(rebuild_pipeline)
    # 设置页增删了项目或模型配置时，顶行候选列表跟着变（选中项若还在则保留）
    window.settings_ctl.projectsChanged.connect(session_ctl.reload)
    window.settings_ctl.profilesChanged.connect(session_ctl.reload)
    # 风格预设增删改后：刷新下拉候选并重建管线（styles 已变化）
    window.settings_ctl.stylesChanged.connect(session_ctl.refreshStyles)
    window.settings_ctl.stylesChanged.connect(rebuild_pipeline)

    app.aboutToQuit.connect(hotkey.unregister)
    app.aboutToQuit.connect(toggle_hotkey.unregister)
    # 退出前先收尾后台线程：QThread 在进程收摊阶段被析构时若仍在运行，
    # Qt 会直接 fatal abort——表现为退出偶发闪退而非报错。
    app.aboutToQuit.connect(window.settings_ctl.shutdown)
    tray.show()

    # 一条生效配置都没有时立即提示（多条生效但未选目标不打扰：主页面下拉
    # 已经高亮提示，用户点到增强时自然会看到）
    if not session_ctl.hasCandidates:
        tray.notify(
            "ContextPilot 没有可用的模型配置",
            "请到设置页「模型配置」添加一条配置，并勾选「已生效」",
        )

    return app.exec()
