import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// 预览窗：顶栏 + 原始指令 + 增强结果（主体）+ 上下文胶囊 + 底部操作栏。
Rectangle {
    id: root
    width: 780
    height: 660
    color: theme.background

    // ---------- 顶栏 ----------
    Item {
        id: topBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: theme.spaceXl
        anchors.rightMargin: theme.spaceXl
        anchors.topMargin: theme.spaceLg
        height: 44

        Row {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            spacing: theme.spaceSm
            Rectangle {
                width: 26; height: 26; radius: theme.radiusSm
                color: theme.accent
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    anchors.centerIn: parent
                    text: "CP"
                    color: theme.textInverse
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    font.weight: Font.Bold
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "ContextPilot"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: statusRow.implicitWidth + theme.spaceMd * 2
            height: 26
            radius: theme.radiusFull
            color: theme.surface
            border.width: 1
            border.color: theme.border
            Row {
                id: statusRow
                anchors.centerIn: parent
                spacing: theme.spaceSm
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7; height: 7; radius: 999
                    color: preview.status.indexOf("失败") === 0 ? theme.danger : theme.success
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: preview.status
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                }
            }
        }
    }

    // ---------- 主体 ----------
    ColumnLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: topBar.bottom
        anchors.bottom: bottomBar.top
        anchors.leftMargin: theme.spaceXl
        anchors.rightMargin: theme.spaceXl
        anchors.topMargin: theme.spaceLg
        anchors.bottomMargin: theme.spaceLg
        spacing: theme.spaceMd

        // 原始指令
        Text {
            text: "原始指令"
            color: theme.textMuted
            font.family: theme.fontFamily
            font.pixelSize: theme.fontCaption
            font.weight: Font.DemiBold
        }
        AppCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 62
            padding: theme.spaceMd
            AppTextArea {
                anchors.fill: parent
                text: preview.originalPrompt
                readOnly: true
            }
        }

        // 增强结果（占据剩余空间）
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spaceSm
            Text {
                text: "增强结果"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
                font.weight: Font.DemiBold
            }
            Text {
                text: "可编辑"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
            }
            Item { Layout.fillWidth: true }
        }
        AppTextArea {
            id: enhancedArea
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: preview.enhancedPrompt
        }

        // 上下文
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: theme.spaceXs
            spacing: theme.spaceSm
            Text {
                text: "上下文"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
                font.weight: Font.DemiBold
            }
            Text {
                text: preview.contextFiles.length === 0 ? "无" : preview.contextFiles.length + " 项"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
            }
        }
        Flow {
            Layout.fillWidth: true
            spacing: theme.spaceSm
            visible: preview.contextFiles.length > 0
            Repeater {
                model: preview.contextFiles
                delegate: Rectangle {
                    required property string modelData
                    height: 26
                    width: chipLabel.implicitWidth + theme.spaceMd * 2
                    radius: theme.radiusFull
                    color: theme.surface
                    border.width: 1
                    border.color: theme.border
                    Text {
                        id: chipLabel
                        anchors.centerIn: parent
                        text: modelData
                        color: theme.textSecondary
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontCaption
                    }
                }
            }
        }
    }

    // ---------- 底部操作栏 ----------
    Item {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: theme.spaceXl
        anchors.rightMargin: theme.spaceXl
        anchors.bottomMargin: theme.spaceLg
        height: 40

        Text {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "Esc 关闭    Enter 使用"
            color: theme.textMuted
            font.family: theme.fontFamily
            font.pixelSize: theme.fontCaption
        }

        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: theme.spaceSm
            AppButton {
                text: "取消"
                variant: "ghost"
                onClicked: preview.close()
            }
            AppButton {
                text: "使用增强 Prompt"
                variant: "primary"
                onClicked: preview.use(enhancedArea.text)
            }
        }
    }
}
