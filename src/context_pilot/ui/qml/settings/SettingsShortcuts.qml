import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「窗口快捷键」：预设方案整体切换 + 逐条自定义。
//
// 规则（与 core/shortcuts.py 一致，UI 只负责呈现与拦截）：
//  - 除「关闭窗口」允许裸 Esc 外，所有绑定必须是组合键——单字母键会在用户
//    打字时被当成命令，是本功能最典型的翻车方式；
//  - 占用复制/粘贴/撤销等文本编辑组合、或组内重复，一律不允许保存；
//  - 与全局热键相同只是 warning（两者命名空间独立，但同按会双触发）。
//
// 改完即时生效：主窗口的 Shortcut 直接绑在 shortcut_ctl 上，不用重启；
// 点底部「保存」才写入 config.toml，下次启动依然成立。
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
            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.spaceMd

                Text {
                    text: "窗口快捷键"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: "这些键只在 ContextPilot 窗口聚焦时生效。改动立即生效，保存后下次启动依然保留。"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                    wrapMode: Text.Wrap
                }

                // ---------- 方案切换 ----------
                AppSegmented {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    segmentMinWidth: 96
                    segmentSpacing: 4
                    options: shortcut_ctl.schemeLabels
                    currentIndex: shortcut_ctl.schemeIndex
                    onActivated: (index) => shortcut_ctl.schemeIndex = index
                }

                Text {
                    Layout.fillWidth: true
                    text: shortcut_ctl.schemeDesc
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    wrapMode: Text.Wrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: theme.border
                }

                // ---------- 逐条自定义 ----------
                Text {
                    text: "逐条自定义"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                    font.weight: Font.DemiBold
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: theme.spaceSm

                    Repeater {
                        model: shortcut_ctl.actions
                        delegate: RowLayout {
                            required property var modelData

                            Layout.fillWidth: true
                            spacing: theme.spaceLg

                            Column {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                spacing: 2

                                Text {
                                    width: parent.width
                                    text: modelData.label
                                    color: theme.textPrimary
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.fontBody
                                }
                                Text {
                                    width: parent.width
                                    visible: text.length > 0
                                    text: modelData.message.length > 0
                                          ? modelData.message : modelData.desc
                                    color: modelData.level === "error" ? theme.danger
                                         : modelData.level === "warning" ? theme.warning
                                         : theme.textMuted
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.fontSmall
                                    wrapMode: Text.Wrap
                                }
                            }

                            AppBindingField {
                                // 便于自动化测试与辅助技术定位到具体动作
                                objectName: "bindingField_" + modelData.id
                                Layout.preferredWidth: 176
                                Layout.preferredHeight: 34
                                Layout.alignment: Qt.AlignVCenter
                                actionId: modelData.id
                                display: modelData.display
                                allowNaked: modelData.allowNaked
                                modified: modelData.modified
                                level: modelData.level
                                message: modelData.message
                            }
                        }
                    }
                }

                // ---------- 整体恢复 ----------
                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spaceSm

                    AppButton {
                        text: "全部恢复方案默认值"
                        variant: "secondary"
                        onClicked: shortcut_ctl.resetAll()
                    }
                    Item { Layout.fillWidth: true }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: theme.border
                }

                Text {
                    Layout.fillWidth: true
                    text: "点击右侧输入框后按下新按键即可改绑：必须是 Ctrl / Alt / Cmd 开头的组合键；"
                          + "「关闭窗口」可另绑 Esc。占用复制/粘贴/撤销等编辑组合，或与其它动作重复，"
                          + "保存时会被拦下。"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
