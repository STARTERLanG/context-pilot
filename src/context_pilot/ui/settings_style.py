"""设置界面的全局 QSS 样式（现代商业软件质感）。

配色基准：背景 #F9FAFB、卡片白 #FFFFFF、边 #E5E7EB、输入边 #D1D5DB、
主文字 #111827、辅助 #6B7280、聚焦/指示 teal #0D9488。
卡片阴影由 Python 的 QGraphicsDropShadowEffect 实现（不在 QSS 中）。
"""

QSS = """
* {
    font-family: "Microsoft YaHei UI", "Inter", "Segoe UI";
    font-size: 13px;
}

/* ---------- 主窗口 ---------- */
#SettingsWindow {
    background: #F9FAFB;
}
#SettingsRoot {
    background: #F9FAFB;
}

/* ---------- 左侧导航 ---------- */
#NavList {
    background: #F3F4F6;
    border: none;
    border-right: 1px solid #E5E7EB;
    outline: 0;
}
#NavList::item {
    height: 40px;
    padding-left: 15px;
    padding-right: 8px;
    color: #4B5563;
    border: none;
    outline: 0;                           /* 去掉默认虚线框 */
    background: transparent;
}
#NavList::item:hover {
    background: #E5E7EB;
    border-radius: 6px;
}
#NavList::item:selected {
    background: #E5E7EB;
    border-radius: 6px;
    color: #111827;
}
/* 注：::item 伪元素不支持 font-weight，选中加粗由
   settings_window._refresh_nav_icons 用 QFont 代码级实现 */

/* ---------- 内容区（居中限宽） ---------- */
#ContentCenter {
    background: #F9FAFB;
}
#ContentColumn {
    background: #F9FAFB;
}

/* ---------- QScrollArea 视口与滚动条 ---------- */
QScrollArea {
    background: #F9FAFB;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: #F9FAFB;
}
/* 现代化滚动条：宽 6px、透明背景、圆角滑块、无上下箭头按钮 */
QScrollArea QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
    border: none;
}
QScrollArea QScrollBar::handle:vertical {
    background: #D1D5DB;
    border-radius: 3px;
    min-height: 30px;
}
QScrollArea QScrollBar::handle:vertical:hover {
    background: #9CA3AF;
}
QScrollArea QScrollBar::sub-line:vertical,
QScrollArea QScrollBar::add-line:vertical {
    height: 0;
    width: 0;
    background: none;
    border: none;
}
QScrollArea QScrollBar::sub-page:vertical,
QScrollArea QScrollBar::add-page:vertical {
    background: transparent;
}

/* ---------- 卡片 ---------- */
#Card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    margin-bottom: 20px;
}
#Card QLabel#Title {
    color: #111827;
    font-size: 14px;
    font-weight: bold;
}
#Card QLabel#Desc {
    color: #6B7280;
    font-size: 12px;
    font-weight: 400;
}
#PageTitle {
    color: #111827;
    font-size: 20px;
    font-weight: bold;
}

/* ---------- 表单控件 ---------- */
/* 注意：QSS min/max-height 作用于内容区，加上 1px 上下边框，
   34 + 2 = 实际总高 36px */
#Card QLineEdit {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding-left: 10px;
    padding-right: 10px;
    min-height: 34px;
    max-height: 34px;
    color: #111827;
    selection-background-color: #99F6E4;
}
#Card QLineEdit:hover {
    border-color: #9CA3AF;
}
#Card QLineEdit:focus {
    border-color: #0D9488;
}

#Card QComboBox {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding-left: 10px;
    padding-right: 10px;
    min-height: 34px;
    max-height: 34px;
    color: #111827;
}
#Card QComboBox:hover {
    border-color: #9CA3AF;
}
#Card QComboBox:focus {
    border-color: #0D9488;
}
/* 原生箭头隐藏（image: none），箭头由 ArrowComboBox 在右侧
   12×12、right:10px 的区域内自绘，与 QSS 定位完全对齐 */
#Card QComboBox::drop-down {
    border: none;
    width: 32px;
    background: transparent;
}
#Card QComboBox::down-arrow {
    image: none;
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 12px;
    height: 12px;
    right: 10px;
}
#Card QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #F3F4F6;
    selection-color: #111827;
    outline: 0;
}

#Card QSpinBox {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding-left: 10px;
    padding-right: 10px;
    min-height: 34px;
    max-height: 34px;
    color: #111827;
}
#Card QSpinBox:focus {
    border-color: #0D9488;
}
/* 极简化数字增减按钮：无背景、无边框，仅保留微小箭头 */
#Card QSpinBox::up-button,
#Card QSpinBox::down-button {
    background: transparent;
    border: none;
    width: 18px;
}
#Card QSpinBox::up-arrow,
#Card QSpinBox::down-arrow {
    width: 7px;
    height: 7px;
}
#Card QSpinBox::up-button:hover,
#Card QSpinBox::down-button:hover {
    background: #F3F4F6;
}

/* ---------- 滑块 ---------- */
#Card QSlider::groove:horizontal {
    height: 4px;
    background: #E5E7EB;
    border-radius: 2px;
}
#Card QSlider::sub-page:horizontal {
    background: #0D9488;
    border-radius: 2px;
}
#Card QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
}
#Card QSlider::handle:horizontal:hover {
    border-color: #0D9488;
}

/* ---------- 开关 ---------- */
/* ToggleSwitch 为手绘 QAbstractButton，不受 QSS 控制（暂不处理样式）。
   以下防御默认 QCheckBox 样式，避免未来误用出现原生外观 */
QCheckBox {
    background: transparent;
    border: none;
    padding: 0;
    spacing: 8px;
}

/* ---------- 按钮 ---------- */
QPushButton#PrimaryButton {
    background: #0D9488;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 24px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background: #0F766E;
}
QPushButton#DangerButton {
    background: #FFFFFF;
    color: #DC2626;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton#DangerButton:hover {
    background: #FEF2F2;
}

/* ---------- 底部状态栏 ---------- */
#StatusBar {
    background: #F9FAFB;
    border: none;
    border-top: 1px solid #F3F4F6;
}
#StatusLabel {
    color: #9CA3AF;
    font-size: 12px;
}
"""
