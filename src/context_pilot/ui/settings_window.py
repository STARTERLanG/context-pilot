"""设置窗口（QWidget 版，严格三层结构）。

第一层：窗口全局背景 #F9FAFB，主布局 QHBoxLayout（左导航 + 右内容）。
第二层：右侧 QScrollArea(widgetResizable=True) 内容器，顶/底各 addStretch(1)，
        中间内容 setMaximumWidth(800) 并以 AlignHCenter 水平居中——窗口拉大时
        内容区保持居中且不超过 800px，绝不无限拉伸。
第三层：卡片（QFrame objectName=Card）内 QVBoxLayout（边距 24、行距 20），
        表单行 = 左文字区固定 400px + addStretch 弹簧 + 右控件固定 240×36。
"""

from pathlib import Path

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

from context_pilot.models.profiles import ModelProfile, ProfileStore
from context_pilot.projects.indexer import Indexer
from context_pilot.projects.projects import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_RUNNING,
    ProjectStore,
)
from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.settings_style import QSS
from context_pilot.ui.widgets import ArrowComboBox, Card, HotkeyEdit, ToggleSwitch

_NAV_ITEMS = (
    ("通用", "gear"),
    ("模型配置", "database"),
    ("项目索引", "folder"),
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
    elif kind == "database":  # 模型配置：圆柱
        p.drawEllipse(3, 3, 10, 4)
        p.drawLine(3, 5, 3, 12)
        p.drawLine(13, 5, 13, 12)
        p.drawEllipse(3, 10, 10, 4)
    elif kind == "folder":  # 项目索引：文件夹
        p.drawRoundedRect(1, 3, 14, 10, 2, 2)
        p.drawLine(1, 6, 15, 6)
    p.end()
    return QIcon(pixmap)


class SettingsWindow(QWidget):
    """设置主窗口。"""

    def __init__(self, model: SettingsModel, base_dir: Path | None = None) -> None:
        super().__init__()
        self._model = model
        self.setObjectName("SettingsWindow")
        self.setWindowTitle("ContextPilot 设置")
        # 模型配置与项目索引用到的存储实例（base_dir 便于测试隔离）
        self._profile_store = ProfileStore(base_dir=base_dir)
        self._project_store = ProjectStore(base_dir=base_dir)
        self._indexer = Indexer(base_dir=base_dir)
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

        # 顺序构建 7 个区块，记录每个区块 widget 供锚点定位
        self._sections: list[QWidget] = []
        for title, builder in (
            ("通用", self._section_general),
            ("模型配置", self._section_profiles),
            ("项目索引", self._section_projects),
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

    # ---------- 模型配置 CRUD ----------
    def _section_profiles(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        self._field_row(
            card, "模型配置", "多套 OpenAI 兼容配置；启用其一生效。点击条目可展开编辑",
            QLabel(""),
        )

        # 新增表单：名称 + Base URL + Key + 获取模型下拉
        add_row = QHBoxLayout()
        add_row.setSpacing(12)

        name_field = QLineEdit()
        name_field.setPlaceholderText("配置名称")
        add_row.addWidget(name_field, 1)

        base_field = QLineEdit()
        base_field.setPlaceholderText("Base URL")
        add_row.addWidget(base_field, 2)

        key_field = QLineEdit()
        key_field.setPlaceholderText("API Key")
        key_field.setEchoMode(QLineEdit.EchoMode.Password)
        add_row.addWidget(key_field, 1)

        model_combo = ArrowComboBox()
        model_combo.addItem("先获取模型")
        add_row.addWidget(model_combo, 2)

        fetch_btn = QPushButton("获取模型")
        fetch_btn.setObjectName("PrimaryButton")
        add_row.addWidget(fetch_btn)

        add_btn = QPushButton("新增")
        add_btn.setObjectName("PrimaryButton")
        add_row.addWidget(add_btn)

        card.addLayout(add_row)
        self._profile_form_status = QLabel("")
        self._profile_form_status.setObjectName("Desc")
        card.addWidget(self._profile_form_status)

        fetch_btn.clicked.connect(
            lambda: self._fetch_models(base_field, key_field, model_combo, fetch_btn)
        )
        add_btn.clicked.connect(
            lambda: self._add_profile(name_field, base_field, key_field, model_combo, layout)
        )

        self._profile_list_card = self._card(layout)
        self._refresh_profile_list()

    def _fetch_models(self, base_field, key_field, model_combo, fetch_btn) -> None:
        """拉取模型列表填充下拉；带加载态与错误反馈。"""
        base_url = base_field.text().strip()
        api_key = key_field.text().strip()
        if not base_url or not api_key:
            self._show_status("请先填写 Base URL 与 API Key", error=True)
            return

        from context_pilot.optimizer.openai_provider import ProviderError, fetch_models

        fetch_btn.setEnabled(False)
        fetch_btn.setText("获取中…")
        self._show_status("正在获取模型列表…")

        class FetchThread(QThread):
            def run(self):
                try:
                    self.models = fetch_models(base_url, api_key)
                    self.error = ""
                except ProviderError as exc:
                    self.models = []
                    self.error = str(exc)

        thread = FetchThread()
        thread.finished.connect(
            lambda: self._on_models_fetched(thread, model_combo, fetch_btn)
        )
        thread.start()
        if not hasattr(self, "_fetch_threads"):
            self._fetch_threads = []
        self._fetch_threads.append(thread)
        thread.finished.connect(lambda: self._fetch_threads.remove(thread))

    def _on_models_fetched(self, thread, model_combo, fetch_btn) -> None:
        fetch_btn.setEnabled(True)
        fetch_btn.setText("获取模型")
        model_combo.clear()
        if thread.error:
            self._show_status(thread.error, error=True)
            return
        model_combo.addItems(thread.models)
        self._show_status(f"获取到 {len(thread.models)} 个模型，请选择")

    def _add_profile(self, name_field, base_field, key_field, model_combo, layout) -> None:
        try:
            self._profile_store.add(
                name=name_field.text().strip(),
                provider="openai",
                base_url=base_field.text().strip(),
                api_key=key_field.text().strip(),
                model=model_combo.currentText().strip(),
                temperature=0.2,
                max_tokens=6000,
                enabled=False,
            )
            name_field.clear(); base_field.clear(); key_field.clear()
            model_combo.clear(); model_combo.addItem("先获取模型")
            self._show_status("已新增模型配置")
        except ValueError as exc:
            self._show_status(str(exc), error=True)
        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        self._rebuild_profile_rows()

    def _rebuild_profile_rows(self) -> None:
        """重建列表行：避免占位布局混乱，逐项生成带展开的条目。"""
        while self._profile_list_card.count():
            item = self._profile_list_card.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profiles = self._profile_store.list()
        if not profiles:
            empty = QLabel("暂无模型配置，请在上方添加")
            empty.setObjectName("Desc")
            self._profile_list_card.addWidget(empty)
            return

        for profile in profiles:
            container = QWidget()
            col = QVBoxLayout(container)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(6)

            # 主行
            row = QHBoxLayout()
            row.setSpacing(12)
            toggle = ToggleSwitch()
            toggle.setChecked(profile.enabled)
            toggle.toggled.connect(
                lambda checked, pid=profile.id: self._toggle_profile(pid, checked)
            )
            row.addWidget(toggle)

            text = QLabel(f"{profile.name}  ·  {profile.model}")
            text.setObjectName("Desc")
            text.setWordWrap(True)
            text.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(text, 1)

            if profile.enabled:
                active = QLabel("生效中")
                active.setObjectName("Desc")
                row.addWidget(active)

            test_btn = QPushButton("测试")
            test_btn.setObjectName("PrimaryButton")
            test_btn.clicked.connect(
                lambda _=False, pid=profile.id, b=test_btn: self._test_profile(pid, b)
            )
            row.addWidget(test_btn)

            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("DangerButton")
            delete_btn.clicked.connect(
                lambda _=False, pid=profile.id: self._delete_profile(pid)
            )
            row.addWidget(delete_btn, 0, Qt.AlignmentFlag.AlignTop)
            col.addLayout(row)

            # 展开编辑区
            edit = QWidget()
            edit.setVisible(False)
            edit_layout = QHBoxLayout(edit)
            edit_layout.setContentsMargins(0, 0, 0, 0)
            edit_layout.setSpacing(12)
            name_edit = QLineEdit(profile.name)
            edit_layout.addWidget(name_edit, 1)
            base_edit = QLineEdit(profile.base_url)
            edit_layout.addWidget(base_edit, 2)
            model_edit = QLineEdit(profile.model)
            edit_layout.addWidget(model_edit, 1)
            save_btn = QPushButton("保存")
            save_btn.setObjectName("PrimaryButton")
            save_btn.clicked.connect(
                lambda _=False, pid=profile.id, ne=name_edit, be=base_edit, me=model_edit:
                self._save_profile(pid, ne.text(), be.text(), me.text())
            )
            edit_layout.addWidget(save_btn)
            col.addWidget(edit)

            # 点击主行文字展开/收起
            text.mousePressEvent = (
                lambda event, e=edit: e.setVisible(not e.isVisible())
            )

            self._profile_list_card.addWidget(container)

    def _toggle_profile(self, profile_id: str, enabled: bool) -> None:
        self._profile_store.set_enabled(profile_id, enabled)
        self._refresh_profile_list()

    def _save_profile(self, profile_id: str, name: str, base_url: str, model: str) -> None:
        self._profile_store.update(
            profile_id, name=name.strip(), base_url=base_url.strip(), model=model.strip()
        )
        self._show_status("已保存修改")
        self._refresh_profile_list()

    def _test_profile(self, profile_id: str, button) -> None:
        """连通性测试：调最小 chat 请求，反馈成功/失败与耗时。"""
        profile = self._profile_store.get(profile_id)
        if profile is None:
            return
        base_url = profile.base_url
        api_key = self._profile_store.reveal_key_by_id(profile_id)
        model = profile.model

        from context_pilot.optimizer.openai_provider import ProviderError, check_connection

        from PySide6.QtCore import QThread

        button.setEnabled(False)
        button.setText("测试中…")

        class TestThread(QThread):
            def run(self):
                try:
                    self.elapsed = check_connection(base_url, api_key, model)
                    self.error = ""
                except ProviderError as exc:
                    self.elapsed = None
                    self.error = str(exc)

        thread = TestThread()
        thread.finished.connect(lambda: self._on_test_done(thread, button))
        thread.start()
        if not hasattr(self, "_test_threads"):
            self._test_threads = []
        self._test_threads.append(thread)
        thread.finished.connect(lambda: self._test_threads.remove(thread))

    def _on_test_done(self, thread, button) -> None:
        button.setEnabled(True)
        button.setText("测试")
        if thread.error:
            self._show_status(f"连通性测试失败：{thread.error}", error=True)
        else:
            self._show_status(f"连通性测试成功，耗时 {thread.elapsed}s")

    def _delete_profile(self, profile_id: str) -> None:
        self._profile_store.delete(profile_id)
        self._refresh_profile_list()

    def _show_status(self, message: str, error: bool = False) -> None:
        self._profile_form_status.setText(message)
        self._profile_form_status.setStyleSheet(
            "color: #DC2626;" if error else "color: #16A34A;"
        )
        from PySide6.QtCore import QTimer

        QTimer.singleShot(4000, lambda: self._profile_form_status.setText(""))

    # ---------- 项目索引 ----------
    def _section_projects(self, layout: QVBoxLayout) -> None:
        card = self._card(layout)
        self._field_row(
            card, "项目索引", "添加本地文件夹路径，手动触发索引；状态实时展示",
            QLabel(""),
        )

        add_row = QHBoxLayout()
        add_row.setSpacing(12)
        path_field = QLineEdit()
        path_field.setPlaceholderText("D:/your/project（绝对路径）")
        add_row.addWidget(path_field, 1)
        add_btn = QPushButton("添加")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(lambda: self._add_project(path_field, layout))
        add_row.addWidget(add_btn)
        card.addLayout(add_row)

        self._project_list_card = self._card(layout)
        self._refresh_project_list()

    def _add_project(self, path_field, layout) -> None:
        path = path_field.text().strip()
        if not path:
            self._project_error("请输入项目路径", layout)
            return
        from pathlib import Path

        if not Path(path).exists():
            self._project_error("路径不存在", layout)
            return
        self._project_store.add(path)
        path_field.clear()
        self._refresh_project_list()

    def _refresh_project_list(self) -> None:
        while self._project_list_card.count():
            item = self._project_list_card.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self._project_store.list()
        if not entries:
            empty = QLabel("暂无项目，请在上方添加文件夹路径")
            empty.setObjectName("Desc")
            self._project_list_card.addWidget(empty)
            return

        for entry in entries:
            row = QHBoxLayout()
            row.setSpacing(12)
            status_text = {
                "pending": "未创建",
                "running": "创建中",
                "done": "已完成",
                "failed": "失败",
            }.get(entry.index_status, entry.index_status)
            label = QLabel(f"{entry.name}  [{status_text}]  {entry.path}")
            label.setObjectName("Desc")
            label.setWordWrap(True)
            row.addWidget(label, 1)
            if entry.error:
                err = QLabel(entry.error)
                err.setObjectName("Desc")
                err.setStyleSheet("color: #DC2626;")
                row.addWidget(err)

            if entry.index_status != STATUS_RUNNING:
                index_btn = QPushButton("创建索引")
                index_btn.setObjectName("PrimaryButton")
                index_btn.clicked.connect(
                    lambda _=False, eid=entry.id: self._index_project(eid)
                )
                row.addWidget(index_btn)

            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("DangerButton")
            delete_btn.clicked.connect(
                lambda _=False, eid=entry.id: self._delete_project(eid)
            )
            row.addWidget(delete_btn)
            self._project_list_card.addLayout(row)

    def _index_project(self, entry_id: str) -> None:
        """后台线程执行索引，避免阻塞 UI；完成后刷新列表。"""
        from PySide6.QtCore import QThread

        entry = self._project_store.get(entry_id)
        if entry is None:
            return

        class IndexWorker(QThread):
            def run(self):
                result = self._indexer.build(self._entry, self._store)
                self._result = result

        worker = IndexWorker()
        worker._indexer = self._indexer
        worker._entry = entry
        worker._store = self._project_store
        worker.finished.connect(self._refresh_project_list)
        worker.start()
        # 持有引用防 GC
        if not hasattr(self, "_index_workers"):
            self._index_workers = []
        self._index_workers.append(worker)
        worker.finished.connect(lambda: self._index_workers.remove(worker))
        self._project_store.set_status(entry_id, STATUS_RUNNING)
        self._refresh_project_list()

    def _delete_project(self, entry_id: str) -> None:
        self._project_store.delete(entry_id)
        self._refresh_project_list()

    def _project_error(self, message: str, layout) -> None:
        err = QLabel(message)
        err.setObjectName("Desc")
        err.setStyleSheet("color: #DC2626;")
        layout.addWidget(err)
        from PySide6.QtCore import QTimer

        QTimer.singleShot(3000, err.deleteLater)

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
