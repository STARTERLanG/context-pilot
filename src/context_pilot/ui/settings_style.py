"""设置界面的全局 QSS 样式（现代 SaaS 极简风）。

配色基准：背景 #F9FAFB、卡片白 #FFFFFF、边 #E5E7EB、输入边 #D1D5DB、
主文字 #111827、辅助 #6B7280、聚焦/指示蓝 #3B82F6。
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
    background: #FFFFFF;
    border: none;
    border-right: 1px solid #E5E7EB;
    outline: 0;
}
#NavList::item {
    height: 40px;
    padding-left: 16px;
    padding-right: 8px;
    color: #374151;
    border: none;
    border-left: 3px solid transparent;   /* 预留选中指示条 */
    background: transparent;
}
#NavList::item:hover {
    background: #F3F4F6;
}
#NavList::item:selected {
    background: #E5E7EB;
    color: #111827;
    font-weight: 600;
    border-left: 3px solid #3B82F6;      /* 左侧蓝色指示条 */
}

/* ---------- 内容区（居中限宽） ---------- */
#ContentCenter {
    background: #F9FAFB;
}
#ContentColumn {
    background: #F9FAFB;
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
    font-weight: 700;
}
#Card QLabel#Desc {
    color: #6B7280;
    font-size: 12px;
    font-weight: 400;
    margin-top: 4px;
}
#PageTitle {
    color: #111827;
    font-size: 20px;
    font-weight: 700;
}

/* ---------- 表单控件 ---------- */
#Card QLineEdit {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 0 10px;
    min-height: 36px;
    max-height: 36px;
    color: #111827;
    selection-background-color: #BFDBFE;
}
#Card QLineEdit:hover {
    border-color: #9CA3AF;
}
#Card QLineEdit:focus {
    border-color: #3B82F6;
}

#Card QComboBox {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 0 10px;
    min-height: 36px;
    max-height: 36px;
    color: #111827;
}
#Card QComboBox:hover {
    border-color: #9CA3AF;
}
#Card QComboBox:focus {
    border-color: #3B82F6;
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

#Card QSpinBox {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 0 10px;
    min-height: 36px;
    max-height: 36px;
    color: #111827;
}
#Card QSpinBox:focus {
    border-color: #3B82F6;
}

/* ---------- 滑块 ---------- */
#Card QSlider::groove:horizontal {
    height: 4px;
    background: #E5E7EB;
    border-radius: 2px;
}
#Card QSlider::sub-page:horizontal {
    background: #3B82F6;
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
    border-color: #3B82F6;
}

/* ---------- 按钮 ---------- */
QPushButton#PrimaryButton {
    background: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 24px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background: #2563EB;
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
