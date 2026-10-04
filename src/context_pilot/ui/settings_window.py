"""设置窗口（QWidget 版，WorkBuddy 风格）。

左导航 220px + 右侧滚动卡片区。数据全部来自 SettingsModel。
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
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.settings_style import QSS
from context_pilot.ui.widgets import ArrowComboBox, Card, HotkeyEdit, ToggleSwitch


class SettingsWindow(QWidget):
    """设置主窗口。"""

    def __init__(self, model: SettingsModel) -> None:
        super().__init__()
        self._model = model
        self.setObjectName("SettingsWindow")
        self.setWindowTitle("ContextPilot 设置")
        self.resize(860, 600)
        self.setStyleSheet(QSS)

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
        nav.setFixedWidth(220)
        nav.setFrameShape(QFrame.Shape.NoFrame)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for label in ("通用", "模型", "快捷键", "记忆", "行为"):
            item = QListWidgetItem(label)
            item.setSizeHint(item.sizeHint())
            nav.addItem(item)
        self._nav = nav
        return nav

    def _switch_page(self, item: QListWidgetItem) -> None:
        self._pages.setCurrentRow(self._nav.row(item))

    # ---------- 右侧内容 ----------
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

    def _scroll_page(self, title: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        page.setStyleSheet("QScrollArea { background: #F9FAFB; }")

        container = QWidget()
        container.setObjectName("SettingsRoot")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        page_title = QLabel(title)
        page_title.setObjectName("PageTitle")
        layout.addWidget(page_title)
        return page, container, layout

    @staticmethod
    def _card_row(card_layout: QVBoxLayout, title: str, desc: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        row.setSpacing(24)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("Title")
        desc_label = QLabel(desc)
        desc_label.setObjectName("Desc")
        desc_label.setWordWrap(True)
        text_col.addWidget(title_label)
        text_col.addWidget(desc_label)

        row.addLayout(text_col, 1)
        row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        card_layout.addLayout(row)

    def _add_card(self, layout: QVBoxLayout) -> tuple[Card, QVBoxLayout]:
        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(18)
        layout.addWidget(card)
        return card, card_layout

    # ---------- 各页 ----------
    def _page_general(self) -> QScrollArea:
        page, container, layout = self._scroll_page("常规")

        card, card_layout = self._add_card(layout)
        self._card_row(card_layout, "项目根目录", "被增强的项目；留空则用启动时的工作目录", self._project_root_input())
        self._card_row(card_layout, "目标 Agent", "增强结果通过剪贴板发送到所选 Agent", self._agent_combo())

        container.setLayout(layout)
        page.setWidget(container)
        return page

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

    def _page_model(self) -> QScrollArea:
        page, container, layout = self._scroll_page("模型")

        card, card_layout = self._add_card(layout)
        self._card_row(card_layout, "提供方", "stub 不联网，仅用于离线验证链路", self._provider_combo())
        self._card_row(card_layout, "接口地址", "任意 OpenAI 兼容端点", self._text_input("baseUrl", "https://api.openai.com/v1"))
        self._card_row(card_layout, "API Key", "只保存在本机配置，不进版本库", self._text_input("apiKey", "", password=True))
        self._card_row(card_layout, "模型名", "如 deepseek-chat / gpt-4o-mini", self._text_input("model", ""))
        self._card_row(card_layout, "超时（秒）", "请求 LLM 的最长等待时间", self._spin_input("timeout", 5, 600, 5))

        container.setLayout(layout)
        page.setWidget(container)
        return page

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

    def _page_hotkey(self) -> QScrollArea:
        page, container, layout = self._scroll_page("快捷键")

        card, card_layout = self._add_card(layout)
        hotkey_edit = HotkeyEdit(self._model.hotkey)
        hotkey_edit.captured.connect(lambda seq: setattr(self._model, "hotkey", seq))
        self._card_row(card_layout, "全局热键", "点击输入框后按下组合键；Esc 取消", hotkey_edit)

        container.setLayout(layout)
        page.setWidget(container)
        return page

    def _page_memory(self) -> QScrollArea:
        page, container, layout = self._scroll_page("记忆")

        card, card_layout = self._add_card(layout)
        toggle = ToggleSwitch()
        toggle.setChecked(self._model.memoryEnabled)
        toggle.toggled.connect(lambda checked: setattr(self._model, "memoryEnabled", checked))
        self._card_row(card_layout, "启用项目记忆", "检索时把项目记忆纳入上下文", toggle)

        # 记忆列表（简单展示 + 删除）
        list_card, list_card_layout = self._add_card(layout)
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
            list_card_layout.addLayout(row)
        if not self._model.memories:
            empty = QLabel("暂无记忆")
            empty.setObjectName("Desc")
            list_card_layout.addWidget(empty)

        container.setLayout(layout)
        page.setWidget(container)
        return page

    def _delete_memory(self, memory_id: str) -> None:
        self._model.deleteMemory(memory_id)

    def _page_behavior(self) -> QScrollArea:
        page, container, layout = self._scroll_page("行为")

        card, card_layout = self._add_card(layout)
        self._card_row(
            card_layout, "开机自启", "登录 Windows 后自动驻留托盘",
            self._toggle("autostart"),
        )
        self._card_row(
            card_layout, "自动写回剪贴板", "点「使用」后自动把结果写入剪贴板",
            self._toggle("autoCopy"),
        )
        self._card_row(
            card_layout, "关闭最小化到托盘", "关窗不退出，仅隐藏到托盘",
            self._toggle("closeToTray"),
        )

        container.setLayout(layout)
        page.setWidget(container)
        return page

    def _toggle(self, prop: str) -> ToggleSwitch:
        toggle = ToggleSwitch()
        toggle.setChecked(getattr(self._model, prop))
        toggle.toggled.connect(lambda checked: setattr(self._model, prop, checked))
        return toggle

    def show_and_activate(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
