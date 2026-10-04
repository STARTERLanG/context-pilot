"""设置窗口（QWidget 版，严格三层结构）。

第一层：窗口全局背景 #F9FAFB，主布局 QHBoxLayout（左导航 + 右内容）。
第二层：右侧 QScrollArea(widgetResizable=True) 内一个容器，其布局
        顶部/底部各 addStretch(1)，中间内容 setFixedWidth(700) 保证整齐。
第三层：卡片（QFrame objectName=Card）内 QVBoxLayout，
        表单行 QHBoxLayout = 左标题+说明 + 弹簧 + 右开关。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.settings_style import QSS
from context_pilot.ui.widgets import ArrowComboBox, Card, HotkeyEdit, ToggleSwitch

_NAV_ITEMS = (
    ("通用", "⚙"),
    ("模型", "\U0001F5A5"),
    ("快捷键", "⌨"),
    ("记忆", "\U0001F4CB"),
    ("行为", "⚛"),
)


class SettingsWindow(QWidget):
    """设置主窗口。"""

    def __init__(self, model: SettingsModel) -> None:
        super().__init__()
        self._model = model
        self.setObjectName("SettingsWindow")
        self.setWindowTitle("ContextPilot 设置")
        self.resize(980, 640)
        self.setStyleSheet(QSS)

        # 第一层：主布局（左导航 + 右内容）
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_nav())
        root.addWidget(self._build_pages(), 1)
        self._nav.itemClicked.connect(self._switch_page)

    # ---------- 左导航 ----------
    def _build_nav(self) -> QListWidget:
        nav = QListWidget()
        nav.setObjectName("NavList")
        nav.setFixedWidth(180)
        nav.setFrameShape(QFrame.Shape.NoFrame)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for label, icon in _NAV_ITEMS:
            item = QListWidgetItem(f"{icon}  {label}")
            item.setSizeHint(item.sizeHint())
            nav.addItem(item)
        nav.setCurrentRow(0)
        self._nav = nav
        return nav

    def _switch_page(self, item: QListWidgetItem) -> None:
        self._pages.setCurrentIndex(self._nav.row(item))

    # ---------- 第二层：右侧内容区 ----------
    def _build_pages(self) -> QStackedWidget:
        self._pages = QStackedWidget()
        for builder in (
            self._page_general,
            self._page_model,
            self._page_hotkey,
            self._page_memory,
            self._page_behavior,
        ):
            self._pages.addWidget(builder())
        return self._pages

    def _page(self, title: str) -> tuple[QScrollArea, QVBoxLayout]:
        """返回 (scroll, 内容布局)：已含顶/底弹簧 + 固定 700px 内容列。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #F9FAFB; border: none; }")

        # 容器：垂直布局，顶部与底部各一根弹簧
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 0, 24, 40)  # 底部 40px padding
        container_layout.addStretch(1)  # 顶部弹簧

        # 中间：固定宽度 700px 的内容列
        content = QWidget()
        content.setFixedWidth(700)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        page_title = QLabel(title)
        page_title.setObjectName("PageTitle")
        content_layout.addWidget(page_title)
        content_layout.addSpacing(8)

        container_layout.addWidget(content, 0, Qt.AlignmentFlag.AlignHCenter)
        container_layout.addStretch(1)  # 底部弹簧

        scroll.setWidget(container)
        return scroll, content_layout

    # ---------- 第三层：卡片与表单行 ----------
    @staticmethod
    def _card(content_layout: QVBoxLayout) -> QVBoxLayout:
        """创建一张卡片（QFrame objectName=Card），返回其内部布局。"""
        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(20)
        content_layout.addWidget(card)
        return card_layout

    @staticmethod
    def _field_row(card_layout: QVBoxLayout, title: str, desc: str, control: QWidget) -> None:
        """一行表单：左标题+说明，弹簧，右控件推到最右。"""
        row = QHBoxLayout()
        row.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("Title")
        desc_label = QLabel(desc)
        desc_label.setObjectName("Desc")
        desc_label.setWordWrap(True)
        text_col.addWidget(title_label)
        text_col.addWidget(desc_label)

        row.addLayout(text_col)
        row.addStretch(1)  # 弹簧：把右侧控件推到最右
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

        card_layout.addLayout(row)

    # ---------- 各页 ----------
    def _page_general(self) -> QScrollArea:
        scroll, layout = self._page("常规")
        card = self._card(layout)
        self._field_row(card, "项目根目录", "被增强的项目；留空则用启动时的工作目录", self._project_root_input())
        self._field_row(card, "目标 Agent", "增强结果通过剪贴板发送到所选 Agent", self._agent_combo())
        return scroll

    def _page_model(self) -> QScrollArea:
        scroll, layout = self._page("模型")
        card = self._card(layout)
        self._field_row(card, "提供方", "stub 不联网，仅用于离线验证链路", self._provider_combo())
        self._field_row(card, "接口地址", "任意 OpenAI 兼容端点", self._text_input("baseUrl", "https://api.openai.com/v1"))
        self._field_row(card, "API Key", "只保存在本机配置，不进版本库", self._text_input("apiKey", "", password=True))
        self._field_row(card, "模型名", "如 deepseek-chat / gpt-4o-mini", self._text_input("model", ""))
        self._field_row(card, "超时（秒）", "请求 LLM 的最长等待时间", self._spin_input("timeout", 5, 600, 5))
        return scroll

    def _page_hotkey(self) -> QScrollArea:
        scroll, layout = self._page("快捷键")
        card = self._card(layout)
        hotkey_edit = HotkeyEdit(self._model.hotkey)
        hotkey_edit.captured.connect(lambda seq: setattr(self._model, "hotkey", seq))
        self._field_row(card, "全局热键", "点击输入框后按下组合键；Esc 取消", hotkey_edit)
        return scroll

    def _page_memory(self) -> QScrollArea:
        scroll, layout = self._page("记忆")
        card = self._card(layout)
        toggle = ToggleSwitch()
        toggle.setChecked(self._model.memoryEnabled)
        toggle.toggled.connect(lambda checked: setattr(self._model, "memoryEnabled", checked))
        self._field_row(card, "启用项目记忆", "检索时把项目记忆纳入上下文", toggle)

        list_card = self._card(layout)
        for memory in self._model.memories:
            row = QHBoxLayout()
            row.setSpacing(12)
            label = QLabel(f"{memory['type']} · {memory['content']}")
            label.setObjectName("Desc")
            label.setWordWrap(True)
            row.addWidget(label, 1)
            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("DangerButton")
            delete_btn.clicked.connect(lambda _=False, mid=memory["id"]: self._delete_memory(mid))
            row.addWidget(delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            list_card.addLayout(row)
        if not self._model.memories:
            empty = QLabel("暂无记忆")
            empty.setObjectName("Desc")
            list_card.addWidget(empty)
        return scroll

    def _page_behavior(self) -> QScrollArea:
        scroll, layout = self._page("行为")
        card = self._card(layout)
        self._field_row(card, "开机自启", "登录 Windows 后自动驻留托盘", self._toggle("autostart"))
        self._field_row(card, "自动写回剪贴板", "点「使用」后自动把结果写入剪贴板", self._toggle("autoCopy"))
        self._field_row(card, "关闭最小化到托盘", "关窗不退出，仅隐藏到托盘", self._toggle("closeToTray"))
        return scroll

    # ---------- 控件工厂 ----------
    def _project_root_input(self) -> QLineEdit:
        field = QLineEdit(self._model.projectRoot)
        field.setPlaceholderText("D:/your/project")
        field.editingFinished.connect(lambda: setattr(self._model, "projectRoot", field.text().strip()))
        return field

    def _agent_combo(self) -> QComboBox:
        combo = ArrowComboBox()
        combo.addItems(["claude", "codex", "gemini"])
        combo.setCurrentText(self._model.agent)
        combo.currentTextChanged.connect(lambda text: setattr(self._model, "agent", text))
        return combo

    def _provider_combo(self) -> QComboBox:
        combo = ArrowComboBox()
        combo.addItems(["stub", "openai"])
        combo.setCurrentText(self._model.provider)
        combo.currentTextChanged.connect(lambda text: setattr(self._model, "provider", text))
        return combo

    def _text_input(self, prop: str, placeholder: str, password: bool = False) -> QLineEdit:
        field = QLineEdit(getattr(self._model, prop))
        field.setPlaceholderText(placeholder)
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        field.editingFinished.connect(lambda: setattr(self._model, prop, field.text().strip()))
        return field

    def _spin_input(self, prop: str, minimum: int, maximum: int, step: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(int(getattr(self._model, prop)))
        spin.valueChanged.connect(lambda value: setattr(self._model, prop, value))
        return spin

    def _toggle(self, prop: str) -> ToggleSwitch:
        toggle = ToggleSwitch()
        toggle.setChecked(getattr(self._model, prop))
        toggle.toggled.connect(lambda checked: setattr(self._model, prop, checked))
        return toggle

    def _delete_memory(self, memory_id: str) -> None:
        self._model.deleteMemory(memory_id)

    def show_and_activate(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
