"""设置界面的全局 QSS 样式（WorkBuddy 风格）。

颜色基准：背景 #F9FAFB、卡片白 #FFFFFF、边 #E5E7EB、
主文字 #111827、次文字 #6B7280、开启青绿 #14B8A6。
"""

QSS = """
* {
    font-family: "Microsoft YaHei", "Inter", "Segoe UI";
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
    background: #FFFFFF;
    border: none;
    border-right: 1px solid #E5E7EB;
    outline: 0;
}
#NavList::item {
    height: 40px;
    padding-left: 20px;
    color: #374151;
    border: none;
    background: transparent;
}
#NavList::item:hover {
    background: #F3F4F6;
}
#NavList::item:selected {
    background: #E5E7EB;
    color: #111827;
    font-weight: 600;
}

/* ---------- 卡片 ---------- */
#Card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
}
#Card QLabel#Title {
    color: #111827;
    font-size: 14px;
    font-weight: 600;
}
#Card QLabel#Desc {
    color: #6B7280;
    font-size: 12px;
}
#PageTitle {
    color: #111827;
    font-size: 20px;
    font-weight: 600;
}

/* ---------- 输入框 ---------- */
#Card QComboBox {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0 12px;
    height: 32px;
    color: #111827;
}
#Card QComboBox:hover {
    border-color: #D1D5DB;
}
#Card QComboBox::drop-down {
    border: none;
    width: 26px;
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

#Card QLineEdit {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0 12px;
    height: 32px;
    color: #111827;
}
#Card QLineEdit:focus {
    border-color: #14B8A6;
}

/* ---------- 滑块 ---------- */
#Card QSlider::groove:horizontal {
    height: 4px;
    background: #E5E7EB;
    border-radius: 2px;
}
#Card QSlider::sub-page:horizontal {
    background: #14B8A6;
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
    border-color: #14B8A6;
}

/* ---------- 按钮 ---------- */
QPushButton#PrimaryButton {
    background: #14B8A6;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 24px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background: #0D9488;
}
QPushButton#PrimaryButton:pressed {
    background: #0F766E;
}

QPushButton#DangerButton {
    background: #FFFFFF;
    color: #DC2626;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 6px 16px;
}
QPushButton#DangerButton:hover {
    background: #FEF2F2;
}
"""
