import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「常规」：上下文预算 + 行为开关（原「上下文」「行为」两个分类合并而来）。
// 预算写回 settings.maxTokens 等（context.*），开关写回 behavior.*，
// 字段语义与旧版 QWidget 设置窗一致，保存入口统一在页面底部。
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

        // ---------- 上下文预算 ----------
        AppSectionCard {
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "上下文预算"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "分项之和不可超过总预算"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "总预算"
                desc: "增强上下文的最大 token 总量"
                AppSpinBox {
                    anchors.centerIn: parent
                    width: 220
                    from: 1000
                    to: 100000
                    stepSize: 500
                    value: settings.maxTokens
                    onValueModified: (value) => settings.maxTokens = value
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "规则预算"
                desc: "项目规则（CLAUDE.md 等）占用的 token"
                AppSpinBox {
                    anchors.centerIn: parent
                    width: 220
                    from: 0
                    to: 100000
                    stepSize: 100
                    value: settings.rulesTokens
                    onValueModified: (value) => settings.rulesTokens = value
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "记忆预算"
                desc: "项目记忆占用的 token"
                AppSpinBox {
                    anchors.centerIn: parent
                    width: 220
                    from: 0
                    to: 100000
                    stepSize: 100
                    value: settings.memoryTokens
                    onValueModified: (value) => settings.memoryTokens = value
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "代码预算"
                desc: "代码检索结果占用的 token"
                AppSpinBox {
                    anchors.centerIn: parent
                    width: 220
                    from: 0
                    to: 100000
                    stepSize: 100
                    value: settings.codeTokens
                    onValueModified: (value) => settings.codeTokens = value
                }
            }
        }

        // ---------- 行为 ----------
        AppSectionCard {
            Text {
                Layout.fillWidth: true
                text: "行为"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "开机自启"
                desc: "登录 Windows 后自动驻留托盘"
                AppToggle {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    checked: settings.autostart
                    onToggled: (checked) => settings.autostart = checked
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "自动写回剪贴板"
                desc: "点「使用」后自动把结果写入剪贴板"
                AppToggle {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    checked: settings.autoCopy
                    onToggled: (checked) => settings.autoCopy = checked
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "关闭最小化到托盘"
                desc: "关窗不退出，仅隐藏到托盘"
                AppToggle {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    checked: settings.closeToTray
                    onToggled: (checked) => settings.closeToTray = checked
                }
            }
        }
    }
}
