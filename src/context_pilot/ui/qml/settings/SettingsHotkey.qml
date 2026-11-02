import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「快捷键」：增强热键 + 界面开关热键。
// 捕获逻辑在 SettingsModel（Qt 键码 → ctrl+shift+… 字符串），本页只负责
// 呈现与取焦点；保存前两者都必须合法且互不相同，校验在保存时统一做。
Flickable {
    id: root
    contentWidth: width
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ScrollBar.vertical: ScrollBar {
        width: 6
        policy: ScrollBar.AsNeeded
        contentItem: Rectangle {
            radius: 3
            color: parent.pressed ? theme.accentHover
                 : parent.hovered ? theme.accent
                 : theme.borderStrong
            opacity: parent.active || parent.hovered || parent.pressed ? 1.0 : 0.6
        }
    }

    ColumnLayout {
        id: column
        width: root.width
        spacing: theme.spaceLg

        AppSectionCard {
            Text {
                Layout.fillWidth: true
                text: "全局快捷键"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "增强热键"
                desc: "读取剪贴板并生成增强提示词；点击输入框后按下组合键，Esc 取消"
                AppHotkeyField {
                    anchors.centerIn: parent
                    width: 220
                    target: "hotkey"
                    text: settings.hotkey
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "显示 / 关闭界面"
                desc: "已显示则隐藏，未显示则弹出；点击输入框后按下组合键，Esc 取消"
                AppHotkeyField {
                    anchors.centerIn: parent
                    width: 220
                    target: "toggle"
                    text: settings.toggleHotkey
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: theme.border
            }

            Text {
                Layout.fillWidth: true
                text: "两个快捷键不能相同；保存后立即重绑，若被其它程序占用会给出提示。"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
                wrapMode: Text.Wrap
            }
        }
    }
}
