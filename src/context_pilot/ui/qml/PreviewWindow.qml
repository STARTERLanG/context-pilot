import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// 预览窗：顶栏 + 原始指令 + 三视图切换（增强/差异/上下文）+ Token 统计 + 底部操作栏。
Rectangle {
    id: root
    width: 820
    height: 680
    color: theme.background

    readonly property var views: ["增强结果", "差异", "上下文"]
    property int currentView: 0

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
            Layout.preferredHeight: 56
            padding: theme.spaceMd
            AppTextArea {
                anchors.fill: parent
                text: preview.originalPrompt
                readOnly: true
            }
        }

        // 视图切换
        AppSegmented {
            Layout.fillWidth: false
            options: root.views
            currentIndex: root.currentView
            onActivated: root.currentView = index
        }

        // ---------- 增强结果 ----------
        AppTextArea {
            id: enhancedArea
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.currentView === 0
            text: preview.enhancedPrompt
        }

        // ---------- 差异视图 ----------
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.currentView === 1
            clip: true
            model: preview.diffRows
            spacing: 0
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width
                height: 26
                color: modelData.kind === "added" ? "#143322"
                     : modelData.kind === "removed" ? "#33161C"
                     : "transparent"

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: theme.spaceMd
                    spacing: theme.spaceMd
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30
                        text: modelData.oldLine !== null ? modelData.oldLine : ""
                        color: theme.textMuted
                        font.family: theme.fontMono
                        font.pixelSize: theme.fontCaption
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30
                        text: modelData.newLine !== null ? modelData.newLine : ""
                        color: theme.textMuted
                        font.family: theme.fontMono
                        font.pixelSize: theme.fontCaption
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20
                        text: modelData.kind === "added" ? "+"
                             : modelData.kind === "removed" ? "−"
                             : " "
                        color: modelData.kind === "added" ? theme.success
                             : modelData.kind === "removed" ? theme.danger
                             : theme.textMuted
                        font.family: theme.fontMono
                        font.pixelSize: theme.fontBody
                        font.weight: Font.Bold
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.text
                        color: modelData.kind === "removed" ? theme.danger
                             : modelData.kind === "added" ? theme.success
                             : theme.textSecondary
                        font.family: theme.fontMono
                        font.pixelSize: theme.fontBody
                        elide: Text.ElideRight
                    }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: preview.diffRows.length === 0
                text: "暂无差异"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
            }
        }

        // ---------- 上下文检查器 ----------
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.currentView === 2
            clip: true
            model: preview.contextRows
            spacing: theme.spaceSm
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width
                height: ctxCol.implicitHeight + theme.spaceMd * 2
                radius: theme.radiusMd
                color: theme.surface
                border.width: 1
                border.color: theme.border

                ColumnLayout {
                    id: ctxCol
                    anchors.fill: parent
                    anchors.margins: theme.spaceMd
                    spacing: theme.spaceXs
                    Row {
                        spacing: theme.spaceSm
                        Text {
                            text: modelData.source
                            color: theme.textPrimary
                            font.family: theme.fontMono
                            font.pixelSize: theme.fontSmall
                            font.weight: Font.DemiBold
                        }
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: typeLabel.implicitWidth + theme.spaceSm * 2
                            height: 18
                            radius: theme.radiusFull
                            color: theme.accentSoft
                            Text {
                                id: typeLabel
                                anchors.centerIn: parent
                                text: modelData.type
                                color: theme.accent
                                font.family: theme.fontFamily
                                font.pixelSize: 10
                            }
                        }
                    }
                    Text {
                        text: "理由：" + modelData.reason
                        color: theme.textSecondary
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSmall
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    Text {
                        text: "相关度 " + modelData.relevance + " · " + modelData.tokens + " tokens"
                        color: theme.textMuted
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontCaption
                    }
                }
            }
        }
    }

    // ---------- 底部：Token 统计 + 操作 ----------
    Item {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: theme.spaceXl
        anchors.rightMargin: theme.spaceXl
        anchors.bottomMargin: theme.spaceLg
        height: 44

        Text {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "原始 " + preview.tokenStats.original
                + " · 上下文 " + preview.tokenStats.context
                + " · 增强 " + preview.tokenStats.enhanced
                + " · 合计 " + preview.tokenStats.total
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
