import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「优化模式」：决定「怎么优化」（结构化增强 / 基础优化 / 专业优化 / 步骤化规划）。
// 新增表单 + 列表（删除模式 / 展开编辑）。内置四档也可编辑 label/长度上限，
// 但 mode 与介绍文案由代码固定，删除前建议保留至少一条可用预设。
Flickable {
    id: root
    contentWidth: width
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    property bool deleteMode: false
    property string expandedId: ""
    property int maxTokensValue: 6000  // 新增表单的长度上限输入值

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

        // ---------- 新增表单 ----------
        AppSectionCard {
            Column {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    width: parent.width
                    text: "新增优化模式"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: "模式决定「怎么优化」；约束指令为空表示沿用该模式的内置系统提示词"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    wrapMode: Text.Wrap
                }
            }

            AppFormRow {
                Layout.fillWidth: true
                label: "名称"
                AppTextField {
                    id: nameField
                    anchors.centerIn: parent
                    width: parent.width
                    placeholderText: "例如：精炼要点"
                }
            }

            // 约束指令：多行文本
            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.spaceXs
                Text {
                    Layout.fillWidth: true
                    text: "约束指令（可选）"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    radius: theme.radiusMd
                    color: theme.surface
                    border.width: 1
                    border.color: instructionArea.activeFocus ? theme.accent : theme.border
                    TextEdit {
                        id: instructionArea
                        anchors.fill: parent
                        anchors.margins: theme.spaceSm
                        wrapMode: TextEdit.Wrap
                        color: theme.textPrimary
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontBody
                        selectByMouse: true
                        Text {
                            anchors.fill: parent
                            text: "例如：只润色、不加标题列表、能短则短"
                            color: theme.textMuted
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontBody
                            visible: instructionArea.text.length === 0
                        }
                    }
                }
            }

            AppFormRow {
                Layout.fillWidth: true
                label: "长度上限"
                AppSpinBox {
                    anchors.centerIn: parent
                    width: 220
                    from: 100
                    to: 100000
                    stepSize: 100
                    value: 6000
                    onValueModified: (value) => maxTokensValue = value
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "新增"
                    variant: "primary"
                    Layout.preferredWidth: 88
                    Layout.preferredHeight: 36
                    onClicked: {
                        if (settingsCtl.addStyle(
                                nameField.text, instructionArea.text, maxTokensValue)) {
                            nameField.text = ""
                            instructionArea.text = ""
                            maxTokensValue = 6000
                        }
                    }
                }
            }
        }

        // ---------- 列表 ----------
        AppSectionCard {
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceMd
                Text {
                    text: "已定义预设"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "删除模式"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                }
                AppToggle {
                    Layout.alignment: Qt.AlignVCenter
                    checked: root.deleteMode
                    onToggled: (checked) => root.deleteMode = checked
                }
            }

                Text {
                    Layout.fillWidth: true
                    visible: settingsCtl.styles.length === 0
                    text: "暂无优化模式，请在上方添加"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                    horizontalAlignment: Text.AlignHCenter
                }

            Repeater {
                model: settingsCtl.styles
                delegate: ColumnLayout {
                    id: item
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: theme.spaceSm
                    property bool expanded: root.expandedId === modelData.id
                    property int itemMaxTokens: modelData.maxTokens

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spaceSm

                        Text {
                            Layout.fillWidth: true
                            text: modelData.label + "  ·  ≈" + modelData.maxTokens + " tokens"
                            color: theme.textPrimary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSmall
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            visible: modelData.builtin
                            Layout.preferredWidth: 40
                            Layout.preferredHeight: 18
                            radius: theme.radiusFull
                            color: theme.surfaceActive
                            Text {
                                anchors.centerIn: parent
                                text: "内置"
                                color: theme.textSecondary
                                font.family: theme.fontFamily
                                font.pixelSize: 10
                            }
                        }

                        AppButton {
                            visible: root.deleteMode
                            text: "删除"
                            variant: "danger"
                            Layout.preferredWidth: 60
                            Layout.preferredHeight: 30
                            onClicked: settingsCtl.deleteStyle(modelData.id)
                        }

                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        TapHandler {
                            onTapped: root.expandedId = item.expanded ? "" : modelData.id
                        }
                    }

                    // ---- 展开编辑区 ----
                    ColumnLayout {
                        visible: item.expanded
                        Layout.fillWidth: true
                        spacing: theme.spaceMd

                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: theme.border
                        }

                        AppFormRow {
                            Layout.fillWidth: true
                            label: "名称"
                            AppTextField {
                                id: itemName
                                anchors.centerIn: parent
                                width: parent.width
                                text: modelData.label
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: theme.spaceXs
                            Text {
                                Layout.fillWidth: true
                                text: "约束指令（可选）"
                                color: theme.textSecondary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontSmall
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 72
                                radius: theme.radiusMd
                                color: theme.surface
                                border.width: 1
                                border.color: itemInstruction.activeFocus ? theme.accent : theme.border
                                TextEdit {
                                    id: itemInstruction
                                    anchors.fill: parent
                                    anchors.margins: theme.spaceSm
                                    text: modelData.instruction
                                    wrapMode: TextEdit.Wrap
                                    color: theme.textPrimary
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.fontBody
                                    selectByMouse: true
                                }
                            }
                        }

                        AppFormRow {
                            Layout.fillWidth: true
                            label: "长度上限"
                            AppSpinBox {
                                anchors.centerIn: parent
                                width: 220
                                from: 100
                                to: 100000
                                stepSize: 100
                                value: modelData.maxTokens
                                onValueModified: (value) => itemMaxTokens = value
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.spaceMd
                            Item { Layout.fillWidth: true }
                            AppButton {
                                text: "取消"
                                variant: "ghost"
                                Layout.preferredWidth: 68
                                Layout.preferredHeight: 32
                                onClicked: root.expandedId = ""
                            }
                            AppButton {
                                text: "保存"
                                variant: "primary"
                                Layout.preferredWidth: 68
                                Layout.preferredHeight: 32
                                onClicked: {
                                    if (settingsCtl.updateStyle(
                                            modelData.id, itemName.text,
                                            itemInstruction.text, itemMaxTokens)) {
                                        root.expandedId = ""
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: theme.border
                    }
                }
            }
        }
    }
}
