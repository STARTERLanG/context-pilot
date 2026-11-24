"""应用装配与入口：QApplication → 单实例 → 托盘/热键/窗口 → 事件循环。

这里也是唯一把配置、提供方与检索器装配起来的地方；引擎模块彼此不感知。
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from context_pilot.adapters.base import AgentAdapter
from context_pilot.adapters.clipboard import claude, codex, gemini
from context_pilot.config import Config, load as load_config
from context_pilot.core.logging_setup import get_logger, setup_logging
from context_pilot.core.models import EnhanceOptions
from context_pilot.core.pipeline import Pipeline
from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore
from context_pilot.ui.memory_manage_controller import MemoryManageController
from context_pilot.optimizer.openai_provider import OpenAiProvider
from context_pilot.optimizer.provider import LlmProvider
from context_pilot.platform.clipboard import write_clipboard_text
from context_pilot.platform.input import (
    focused_control,
    foreground_window,
    grab_selected_text,
    write_and_paste,
)
from context_pilot.platform.single_instance import SingleInstance
from context_pilot.shortcuts import HotkeyRegistrationError, ShortcutManager
from context_pilot.retrieval.base import Retriever
from context_pilot.ui.icon import app_icon
from context_pilot.ui.memory_controller import MemoryController
from context_pilot.ui.preview_model import PreviewModel
from context_pilot.ui.preview_window import PreviewWindow
from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.session_controller import SessionController
from context_pilot.ui.toast import toast
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
            # 项目库 + 全局库一起检索：全局记忆（跨项目的偏好/约定）对所有
            # 项目生效；任一库打不开时仍用能打开的那个，不让主流程失败。
            project_store = MemoryStore(project_root)
            try:
                global_store = MemoryStore("", scope="global")
            except OSError:
                global_store = None
            retrievers.append(
                MemoryRetriever(project_store, global_store=global_store)
            )
        except OSError:
            # 项目记忆库不可用时，仍尝试只用全局库
            try:
                retrievers.append(MemoryRetriever(MemoryStore("", scope="global")))
            except OSError:
                pass
    return retrievers


def _build_adapter(config: Config) -> AgentAdapter:
    agents = {"claude": claude, "codex": codex, "gemini": gemini}
    return agents.get(config.general.agent, claude)()


def _set_app_user_model_id(log) -> None:
    """让 Windows 把这个进程认作独立应用，而不是「python.exe」。

    Windows 任务栏按 AppUserModelID 归组并取图标：用 python.exe 启动时，
    进程身份默认是 Python，任务栏显示 Python 图标，setWindowIcon 盖不住。
    显式声明身份后任务栏改用窗口图标（设置失败也不阻断启动，只是回退到旧行为）。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        api = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        api.argtypes = (ctypes.c_wchar_p,)
        api("ContextPilot.ContextPilot")
    except (AttributeError, OSError) as exc:
        log.debug("设置 AppUserModelID 失败，任务栏图标可能回退到 python.exe: %s", exc)


def main() -> int:
    # 尽早初始化日志：此后的装配、检索、增强失败都能留下现场（PRD 三十六章）。
    # 文件不可用时自动降级到 stderr，不会因此启动失败。
    setup_logging()
    log = get_logger(__name__)

    # 必须在任何窗口创建前声明应用身份，否则任务栏仍按 python.exe 取图标
    _set_app_user_model_id(log)

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
    # 复用上面已加载（或已回退）的配置：SettingsModel 再读一次文件会让
    # 损坏的 config.toml 在启动后半段再次抛异常，前面的兜底等于白做。
    settings_model = SettingsModel(config=config)
    # 主页面「项目 / 模型」选择：项目只活在会话内存里，增强目标跨启动保留
    session_ctl = SessionController(config)
    # 记忆候选控制器：按当前项目隔离记忆库；下面 rebuild_pipeline 时同步归属
    memory_ctl = MemoryController(session_ctl.current_project_root)
    memory_manage_ctl = MemoryManageController(session_ctl.current_project_root)
    try:
        window = PreviewWindow(
            model,
            settings=settings_model,
            session=session_ctl,
            memory=memory_ctl,
            memory_manage=memory_manage_ctl,
            on_close=lambda: _handle_close(state, app),
        )
    except Exception:
        # QML 缺失 / 语法错误 / 部署损坏时给出可诊断的失败，而不是裸异常退出
        log.exception("界面初始化失败（QML 加载或上下文属性错误）")
        print("ContextPilot 界面初始化失败，请查看日志", file=sys.stderr)
        return 1
    tray = Tray()
    # 快捷键统一由 ShortcutManager 装配：全局热键（增强 / 界面开关）按 name 登记，
    # 内部自增 hotkey_id 保证互不相同；窗口内快捷键的绑定表也由它持有。
    shortcuts = ShortcutManager()

    # QThread 被 GC 会崩，需持有引用
    running_workers: list[EnhanceWorker] = []

    def _discard_worker(worker: EnhanceWorker) -> None:
        """线程结束后从持有列表移除（退出清表后可能已不存在，需幂等）。"""
        if worker in running_workers:
            running_workers.remove(worker)

    def shutdown_workers() -> None:
        """退出前等待增强线程结束。

        EnhanceWorker 没有 parent，进程收摊时随局部变量一起析构；若此时
        run() 还在阻塞（httpx 请求最长 60s），Qt 会直接 abort。这里用
        wait() 同步收尾，宁可退出慢几秒，也不能闪退或丢掉已发起的增强。
        """
        for worker in list(running_workers):
            if worker.isRunning():
                log.info("等待增强线程结束再退出")
                worker.wait()
        running_workers.clear()

    def rebuild_pipeline() -> None:
        """按当前「项目 / 模型」选择重建管线：下一次增强立即按新选择执行。

        扫描失败时不替换旧管线——界面应该还能用上一次可用的配置继续工作，
        失败原因走底部状态栏告知。
        """
        cfg = state["config"]
        # 「无项目」时 current_project_root 为空串，project_root 传 None：
        # Pipeline 据此跳过仓库扫描与检索器构建（仅保留 provider）。
        root_str = session_ctl.current_project_root
        # 记忆库归属跟着项目走：切项目后旧候选必须失效，否则会把 A 项目的
        # 决策写进 B 项目的库。set_project_root 内部在变化时清空候选。
        memory_ctl.set_project_root(root_str)
        # 设置页记忆栏跟随项目切换（全局栏不受影响）
        memory_manage_ctl.set_project_root(root_str)
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

    def _build_hotkey_pipeline(cfg: Config) -> Pipeline | None:
        """按「增强热键默认模型 + 默认项目」构建独立管线；无可用模型时返回 None。

        全局热键在任意应用里触发，与主窗口顶行的「项目 / 模型」选择无关，故用
        热键专用的默认值构建。默认项目指定了某个已索引项目时，会检索该项目代码
        作为上下文；为「无项目」时仅优化文本、不检索代码。

        默认模型回落规则：
        1. 指定了 default_model_id 且该配置已生效 → 用它；
        2. 未指定 → 回落主窗口当前选中的目标；
        3. 都没有 → 返回 None，由调用方提示。
        """
        hk = cfg.enhance_hotkey
        target = session_ctl.provider_target_by_id(hk.default_model_id)
        if target is None:
            # 回落：未指定或不可用时，用主窗口当前选中目标（仅当可用）
            target = session_ctl.provider_target()
        if target is None:
            return None
        provider = _build_provider(cfg, target)
        if not target.get("api_key") or not target.get("model"):
            return None
        # 默认项目：指定了已索引项目则检索其代码，否则无项目（仅优化文本）
        root_str = session_ctl.project_root_by_id(hk.default_project_id)
        root = Path(root_str) if root_str else None
        return Pipeline(
            project_root=root,
            provider=provider,
            extra_retrievers=_build_retrievers(cfg, root) if root is not None else [],
            styles=session_ctl.style_objects(),
            budget=cfg.context.as_budget(),
        )

    def on_enhance() -> None:
        # 全局增强热键：按「增强热键默认值」配置执行。
        #
        # - auto_paste 开启：自动全选当前输入框 → 复制 → 增强 → 粘贴回写。
        # - auto_paste 关闭：只复制用户已选中的文本 → 增强 → 结果写回剪贴板，
        #   由用户自行粘贴，不抢窗口焦点、不回写。
        #
        # 默认模式 / 默认模型是热键专用值（config.enhance_hotkey），与主窗口
        # 顶行的当前选择相互独立：后台触发时主窗口的选择可能早已被切走。
        #
        # 用 QTimer 延迟一拍再抓取：WM_HOTKEY 回调触发时，用户物理键盘上的
        # Ctrl/Shift 可能还没完全松开，立即 SendInput 模拟 Ctrl+A/C/V 会与
        # 物理修饰键状态叠加导致失效。延迟 ~120ms 等按键复位。
        def _grab_impl() -> None:
            hk = state["config"].enhance_hotkey
            auto_paste = hk.auto_paste

            # 1) 抓取文本：auto_paste 时全选复制，否则只复制已选中内容
            hwnd = foreground_window()
            # 趁热键触发当下记录焦点控件：增强耗时数秒，期间目标窗口内部的
            # 焦点可能转移，回写时要把焦点还回这个控件，粘贴才落对地方。
            focus = focused_control(hwnd) if hwnd else None
            if auto_paste:
                log.info("增强热键触发（自动粘贴）：全选并复制当前输入框")
            else:
                log.info("增强热键触发（手动粘贴）：复制当前选中文本")

            # 读写剪贴板与按键注入都在 grab_selected_text 内完成，返回 None
            # 表示确实没抓到（而不是「抓到了空串」），据此区分提示语。
            prompt = grab_selected_text(select_all_first=auto_paste)
            if prompt is None:
                log.warning(
                    "未抓取到文本（剪贴板无内容）hwnd=%s focus=%s", hwnd, focus
                )
                hint = "请先聚焦输入框" if auto_paste else "请先选中要增强的内容"
                toast("未获取到文本", hint, kind="warning")
                return
            log.info("抓取到文本（长度=%d）hwnd=%s focus=%s", len(prompt), hwnd, focus)

            if not prompt.strip():
                log.warning("抓取到的文本为空，中止增强")
                hint = "输入框是空的" if auto_paste else "请先选中要增强的内容"
                toast("未获取到文本", hint, kind="warning")
                return

            # 2) 解析默认模型（独立于主窗口选择），构建独立 pipeline
            pipeline = _build_hotkey_pipeline(state["config"])
            # 热键默认项目独立于主窗口选择：记忆也要归到这个项目，
            # 不能因为主窗口此刻停在别的项目就把候选写错库。
            hotkey_root = session_ctl.project_root_by_id(hk.default_project_id)
            if pipeline is None:
                log.warning("无可用默认模型，中止增强")
                toast("无可用模型", "请到设置页勾选已生效模型并指定默认模型", kind="warning")
                return

            # 3) 进行中：小号轻提示
            toast("增强中…", "正在优化文本", kind="info", compact=True, duration=1800)

            def _write_back(result) -> None:
                log.info("增强成功，结果长度=%d", len(result.enhanced_prompt))
                # 从用户原文抽取候选（不是增强后的任务书），归到热键默认项目。
                # 热键路径不弹窗打断：候选留给预览窗的「记忆」角标，由用户主动确认。
                memory_ctl.set_project_root(hotkey_root)
                memory_ctl.collect(result.original_prompt)
                if auto_paste:
                    # 自动粘贴：切前台 + 还焦点 + Ctrl+V，回写覆盖已全选的原文
                    ok = write_and_paste(hwnd, result.enhanced_prompt, focus)
                    log.info(
                        "回写%s（hwnd=%s focus=%s）", "成功" if ok else "失败", hwnd, focus
                    )
                    if not ok:
                        # 切前台或按键投递失败：结果已在剪贴板里，退化为手动粘贴
                        write_clipboard_text(result.enhanced_prompt)
                        toast("增强完成", "已复制到剪贴板，请手动粘贴（Ctrl+V）", kind="success")
                    else:
                        toast("增强完成", "已自动回写", kind="success")
                else:
                    # 仅返回结果：写入剪贴板，用户自行粘贴
                    write_clipboard_text(result.enhanced_prompt)
                    toast("增强完成", "结果已复制到剪贴板，请粘贴（Ctrl+V）", kind="success")

            def _on_failed(message: str) -> None:
                log.warning("增强失败：%s", message)
                toast("增强失败", message, kind="danger")

            _run_enhance(
                prompt,
                on_success=_write_back,
                on_failure=_on_failed,
                pipeline=pipeline,
                style=hk.default_style,
                include_context=bool(hotkey_root),
            )

        def _grab() -> None:
            """热键入口的兜底包装。

            这段逻辑跑在 QTimer 回调里，异常不会进应用日志、也没有任何 UI 反馈
            ——表现为「按了热键只弹了一下进行中提示，然后彻底没反应」，极难排查。
            故统一在这里兜住：失败必须留在日志里、并且让用户看见原因。
            """
            try:
                _grab_impl()
            except Exception as exc:  # UI 边界：任何异常都要有可见反馈
                log.exception("增强热键处理异常：%s", exc)
                toast("增强失败", f"内部错误：{exc}", kind="danger")

        QTimer.singleShot(120, _grab)

    def _run_enhance(
        text: str, *, on_success, on_failure, pipeline=None, style=None,
        include_context=None,
    ) -> None:
        """发起一次增强，结果/失败分别交给 on_success / on_failure 回调。

        这是「增强」的统一执行点：窗口内按钮走 on_enhance_requested（结果进
        预览窗），全局热键走 on_enhance（结果静默回写输入框）。两者共享同一套
        EnhanceOptions 构建与 worker 生命周期管理，避免两条链路各写一份。

        pipeline 缺省用主窗口管线；全局热键传入按「默认模型 / 默认项目」构建的
        独立管线。style 缺省取主窗口顶行选中风格；全局热键传入「默认模式」。
        include_context 缺省按是否选中项目判断；全局热键按默认项目是否指定传入。
        """
        use_style = style if style is not None else session_ctl.current_style
        style_obj = session_ctl.style_store.get(use_style)
        max_tokens = style_obj.max_tokens if style_obj else 6000
        if include_context is None:
            # 主窗口链路：有项目就检索代码；全局热键未显式传入时按无项目处理
            include_context = session_ctl.has_project if pipeline is None else False
        options = EnhanceOptions(
            include_context=include_context,
            style=use_style,
            max_tokens=max_tokens,
        )
        # 显式判 None：Pipeline 未来若实现 __len__/__bool__，`or` 会把空管线
        # 误判为 False，导致热键专用管线被主窗口管线悄悄顶替。
        effective_pipeline = pipeline if pipeline is not None else state["pipeline"]
        worker = EnhanceWorker(effective_pipeline, text, options=options)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_failure)
        worker.finished.connect(lambda: _discard_worker(worker))
        running_workers.append(worker)
        worker.start()

    def on_enhance_requested(text: str) -> None:
        def _success(result) -> None:
            model.set_result(result)
            # 用回传的 original_prompt（即本次真正提交的原文）抽候选，归到
            # 主窗口当前项目；切项目时 set_project_root 已先清过旧候选。
            memory_ctl.collect(result.original_prompt)

        _run_enhance(text, on_success=_success, on_failure=model.set_failed)

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
        for name, sequence, title in (
            ("enhance", new_config.general.hotkey, "增强热键未能应用"),
            ("toggle", new_config.general.toggle_hotkey, "界面开关热键未能应用"),
        ):
            try:
                shortcuts.rebind_global(name, sequence)
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
        shortcuts.unregister_all_globals()
        app.quit()

    for name, sequence, title, log_label in (
        ("enhance", config.general.hotkey, "ContextPilot 热键不可用", "增强热键"),
        ("toggle", config.general.toggle_hotkey, "界面开关热键不可用", "界面开关热键"),
    ):
        try:
            shortcuts.register_global(name, sequence)
            log.info("%s已注册：%s", log_label, shortcuts.query_global(name))
        except HotkeyRegistrationError as exc:
            log.warning("%s注册失败（%s）：%s", log_label, sequence, exc)
            tray.notify(title, str(exc))

    hotkey = shortcuts.get_global("enhance")
    toggle_hotkey = shortcuts.get_global("toggle")
    hotkey.pressed.connect(on_enhance)
    toggle_hotkey.pressed.connect(on_toggle_window)
    model.useRequested.connect(on_use)
    model.enhanceRequested.connect(on_enhance_requested)
    model.closeRequested.connect(window.hide)
    tray.showRequested.connect(on_toggle_window)
    tray.settingsRequested.connect(on_settings)
    tray.quitRequested.connect(on_quit)
    settings_model.saved.connect(on_saved)
    # 保存失败（热键重复 / 预算超额 / 落盘异常）：显示页内保存栏即可，不必打扰托盘
    settings_model.saveFailed.connect(
        lambda msg: window.settings_ctl.notify(msg, error=True)
    )
    instance.show_requested.connect(on_toggle_window)
    # 顶行「项目 / 模型」切换：立即按新选择重建管线
    session_ctl.selectionChanged.connect(rebuild_pipeline)
    # 设置页增删了项目或模型配置时，顶行候选列表跟着变（选中项若还在则保留）
    window.settings_ctl.projectsChanged.connect(session_ctl.reload)
    window.settings_ctl.profilesChanged.connect(session_ctl.reload)
    # 风格预设增删改后：刷新下拉候选并重建管线（styles 已变化）
    window.settings_ctl.stylesChanged.connect(session_ctl.refreshStyles)
    window.settings_ctl.stylesChanged.connect(rebuild_pipeline)

    app.aboutToQuit.connect(shortcuts.unregister_all_globals)
    # 退出前先收尾后台线程：QThread 在进程收摊阶段被析构时若仍在运行，
    # Qt 会直接 fatal abort——表现为退出偶发闪退而非报错。
    app.aboutToQuit.connect(window.settings_ctl.shutdown)
    app.aboutToQuit.connect(shutdown_workers)
    tray.show()

    # 一条生效配置都没有时立即提示（多条生效但未选目标不打扰：主页面下拉
    # 已经高亮提示，用户点到增强时自然会看到）
    if not session_ctl.hasCandidates:
        tray.notify(
            "ContextPilot 没有可用的模型配置",
            "请到设置页「模型配置」添加一条配置，并勾选「已生效」",
        )

    return app.exec()
