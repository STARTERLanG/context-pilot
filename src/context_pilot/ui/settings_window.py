"""设置窗口（QWidget 版，严格三层结构）。

第一层：窗口全局背景 #F9FAFB，主布局 QHBoxLayout（左导航 + 右内容）。
第二层：右侧 QScrollArea(widgetResizable=True) 内容器，顶/底各 addStretch(1)，
        中间内容 setMaximumWidth(800) 并以 AlignHCenter 水平居中——窗口拉大时
        内容区保持居中且不超过 800px，绝不无限拉伸。
第三层：卡片（QFrame objectName=Card）内 QVBoxLayout（边距 24、行距 20），
        表单行 = 左文字区固定 400px + addStretch 弹簧 + 右控件固定 240×36。
"""

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.settings_style import QSS
from context_pilot.ui.widgets import ArrowComboBox, Card, HotkeyEdit, ToggleSwitch

_NAV_ITEMS = (
    ("通用", "gear"),
    ("模型", "chip"),
    ("上下文", "sliders"),
    ("快捷键", "keyboard"),
    ("记忆", "list"),
    ("行为", "bolt"),
)


def _nav_icon(kind: str, color: str = "#6B7280") -> QIcon:
    """程序化绘制 16×16 单色导航图标（与 tray 同风格，免二进制资源，大小绝对一致）。

    color 参数允许选中态用强调色重绘，实现图标随选中高亮。
    """
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "gear":  # 通用：齿轮
        p.drawEllipse(3, 3, 10, 10)
        p.drawEllipse(6.5, 6.5, 3, 3)
        for x1, y1, x2, y2 in ((8, 1, 8, 3), (8, 13, 8, 15), (1, 8, 3, 8), (13, 8, 15, 8)):
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
    elif kind == "chip":  # 模型：芯片
        p.drawRect(3, 3, 10, 10)
        p.drawRect(6, 6, 4, 4)
        for v in (5, 8, 11):
            p.drawLine(v, 1, v, 3)
            p.drawLine(v, 13, v, 15)
    elif kind == "keyboard":  # 快捷键：键盘
        p.drawRect(1, 4, 14, 8)
        for x in (4, 6, 8, 10, 12):
            p.drawPoint(x, 7)
        p.drawLine(4, 10, 12, 10)
    elif kind == "list":  # 记忆：列表
        for y in (4, 8, 12):
            p.drawPoint(3, y)
            p.drawLine(6, y, 13, y)
    elif kind == "sliders":  # 上下文：预算滑块（三条横线 + 圆点）
        for y, x in ((4, 7), (8, 5), (12, 9)):
            p.drawLine(3, y, 13, y)
            p.setBrush(QColor("#6B7280"))
            p.drawEllipse(x - 1.5, y - 1.5, 3, 3)
            p.setBrush(Qt.BrushStyle.NoBrush)
    elif kind == "bolt":  # 行为：闪电
        p.drawPolygon(
            QPolygonF(
                [
                    QPointF(9.5, 1.5),
                    QPointF(4.0, 9.0),
                    QPointF(7.5, 9.0),
                    QPointF(6.0, 14.5),
                    QPointF(12.0, 6.5),
                    QPointF(8.5, 6.5),
                ]
            )
        )
    p.end()
    return QIcon(pixmap)


class SettingsWindow(QWidget):
    """设置主窗口。"""

    def __init__(self, model: SettingsModel) -> None:
        super().__init__()
        self._model = model
        self.setObjectName("SettingsWindow")
        self.setWindowTitle("ContextPilot 设置")
        # 单页滚动布局：行最小内容宽 612（文字320+间距24+控件220+卡片边距48），
        # 加导航 180 与页边距 48 = 840，窗口最小宽度与之持平，保证内容完整显示。
        self.resize(860, 600)
        self.setMinimumSize(840, 520)
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
        nav.setIconSize(QSize(16, 16))
        nav.setFrameShape(QFrame.Shape.NoFrame)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for label, kind in _NAV_ITEMS:
            item = QListWidgetItem(_nav_icon(kind), f" {label}")  # 前置空格 ≈ 图标与文字 10px 间距
            item.setSizeHint(QSize(item.sizeHint().width(), 40))  # 统一 item 高 40px
            # 缓存该 item 的 kind，供选中态重绘 teal 图标
            item.setData(Qt.ItemDataRole.UserRole, kind)
            nav.addItem(item)
        nav.setCurrentRow(0)
        # 选中变化时重绘图标颜色：选中 teal，其余灰
        nav.currentRowChanged.connect(self._refresh_nav_icons)
        self._nav = nav
        return nav

    def _refresh_nav_icons(self, current_row: int) -> None:
        """选中项图标变强调色 teal、文字加粗，其余保持灰色常规字重。

        QSS 的 ::item 伪元素不支持 font-weight（Qt 限制），加粗须用 QFont
        在代码级设置；与图标重绘共用同一钩子，保证同步刷新。
        """
        for row in range(self._nav.count()):
            item = self._nav.item(row)
            kind = item.data(Qt.ItemDataRole.UserRole)
            color = "#0D9488" if row == current_row else "#6B7280"
            item.setIcon(_nav_icon(kind, color))
            font = item.font()
            font.setBold(row == current_row)
            item.setFont(font)

    def _switch_page(self, item: QListWidgetItem) -> None:
        """点击导航 → 快速定位（滚动）到对应区块，而非切换页面。"""
        row = self._nav.row(item)
        if 0 <= row < len(self._sections):
            widget = self._sections[row]
            # 滚动到区块顶部（相对滚动区内容坐标）
            self._scroll.verticalScrollBar().setValue(widget.y())

    # ---------- 第二层：右侧内容区（单页滚动 + 锚点定位） ----------
    def _build_pages(self) -> QScrollArea:
        """构建单个滚动内容区：顺序堆叠所有「标题+卡片」区块。

        点击左侧导航不切页，而是滚动到对应区块；滚动时高亮当前区块对应的导航项。
        """
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 32)
        container_layout.setSpacing(0)

        # 内容列：限宽 612（行最小内容宽）、水平居中
        content = QWidget()
        content.setMaximumWidth(612)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 顺序构建 5 个区块，记录每个区块 widget 供锚点定位
        self._sections: list[QWidget] = []
        for title, builder in (
            ("通用", self._section_general),
            ("模型", self._section_model),
            ("上下文", self._section_context),
            ("快捷键", self._section_hotkey),
            ("记忆", self._section_memory),
            ("行为", self._section_behavior),
        ):
            section = QWidget()
            sec_layout = QVBoxLayout(section)
            sec_layout.setContentsMargins(0, 0, 0, 0)
            sec_layout.setSpacing(0)

            page_title = QLabel(title)
            page_title.setObjectName("PageTitle")
            sec_layout.addWidget(page_title)
            sec_layout.addSpacing(20)  # 标题与卡片间距

            builder(sec_layout)  # 向区块内添加卡片

            content_layout.addWidget(section)
            content_layout.addSpacing(32)  # 区块之间间距
            self._sections.append(section)

        # 居中包裹
        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch(1)
        center_row.addWidget(content, 1)
        center_row.addStretch(1)
        container_layout.addLayout(center_row)
        container_layout.addStretch(1)

        self._scroll.setWidget(container)

        # 滚动时更新导航高亮
        self._scroll.verticalScrollBar().valueChanged.connect(self._sync_nav_on_scroll)
        return self._scroll

    def _sync_nav_on_scroll(self, value: int) -> None:
        """根据滚动位置高亮当前所在区块对应的导航项。"""
        # 阻断递归（程序化 setCurrentRow 不触发 itemClicked，这里无副作用，直接设置）
        for i, section in enumerate(self._sections):
            # 区块顶部（含容器上边距 24）
            top = section.y() + 24
            if value < top + section.height() - 40:
                if self._nav.currentRow() != i:
                    self._nav.setCurrentRow(i)
                return
        if self._nav.currentRow() != len(self._sections) - 1:
            self._nav.setCurrentRow(len(self._sections) - 1)

    # ---------- 第三层：卡片与表单行 ----------
    @staticmethod
    def _card(content_layout: QVBoxLayout) -> QVBoxLayout:
        """创建一张卡片（QFrame objectName=Card），返回其内部布局（padding 24 / 行距 20）。"""
        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(20)

        # 极淡投影：BlurRadius=15、偏移 (0,2)、半透明黑，营造卡片悬浮层次
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 15))
        card.setGraphicsEffect(shadow)

        content_layout.addWidget(card)
        return card_layout

    @staticmethod
    def _field_row(card_layout: QVBoxLayout, title: str, desc: str, control: QWidget) -> None:
        """一行表单：左文字区固定 320px + addStretch 弹簧 + 右控件固定 220×36。

        行最小内容宽 = 320 + 24(间距) + 220 + 48(卡片边距) = 612，
        加导航 180 与页边距 48 = 840，与窗口最小宽度一致，保证内容完整显示。
        """
        row = QHBoxLayout()
        row.setSpacing(24)
        row.setContentsMargins(0, 0, 0, 0)

        # 左侧文字区：固定 320px，说明文字在区内自动换行
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)  # 标题与说明间距 4px
        title_label = QLabel(title)
        title_label.setObjectName("Title")
        desc_label = QLabel(desc)
        desc_label.setObjectName("Desc")
        desc_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)
        text_widget.setFixedWidth(320)

        row.addWidget(text_widget)
        row.addStretch(1)  # 弹簧：把右侧控件推到最右
        # 开关自带固定尺寸（40×22），其余输入控件统一 220×36
        if not isinstance(control, ToggleSwitch):
            control.setFixedWidth(220)
            control.setFixedHeight(36)
        control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

        card_layout.addLayout(row)

    # ---------- 各区块（向传入布局添加卡片，不返回滚动区） ----------
    def _section_general(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        self._field_row(card, "项目根目录", "被增强的项目；留空则用启动时的工作目录", self._project_root_input())
        self._field_row(card, "目标 Agent", "增强结果通过剪贴板发送到所选 Agent", self._agent_combo())

    def _section_model(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        self._field_row(card, "提供方", "stub 不联网，仅用于离线验证链路", self._provider_combo())
        self._field_row(card, "接口地址", "任意 OpenAI 兼容端点", self._text_input("baseUrl", "https://api.openai.com/v1"))
        self._field_row(card, "API Key", "只保存在本机配置，不进版本库", self._text_input("apiKey", "", password=True))
        self._field_row(card, "模型名", "如 deepseek-chat / gpt-4o-mini", self._text_input("model", ""))
        self._field_row(card, "超时（秒）", "请求 LLM 的最长等待时间", self._spin_input("timeout", 5, 600, 5))

    def _section_context(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        self._field_row(card, "总预算", "增强上下文的最大 token 总量", self._spin_input("maxTokens", 1000, 100000, 500))
        self._field_row(card, "规则预算", "项目规则（CLAUDE.md 等）占用的 token", self._spin_input("rulesTokens", 0, 100000, 100))
        self._field_row(card, "记忆预算", "项目记忆占用的 token", self._spin_input("memoryTokens", 0, 100000, 100))
        self._field_row(card, "代码预算", "代码检索结果占用的 token", self._spin_input("codeTokens", 0, 100000, 100))

    def _section_hotkey(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        hotkey_edit = HotkeyEdit(self._model.hotkey)
        hotkey_edit.captured.connect(lambda seq: setattr(self._model, "hotkey", seq))
        self._field_row(card, "全局热键", "点击输入框后按下组合键；Esc 取消", hotkey_edit)

    def _section_memory(self, layout: QVBoxLayout) -> None:
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

    def _section_behavior(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        self._field_row(card, "开机自启", "登录 Windows 后自动驻留托盘", self._toggle("autostart"))
        self._field_row(card, "自动写回剪贴板", "点「使用」后自动把结果写入剪贴板", self._toggle("autoCopy"))
        self._field_row(card, "关闭最小化到托盘", "关窗不退出，仅隐藏到托盘", self._toggle("closeToTray"))

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
