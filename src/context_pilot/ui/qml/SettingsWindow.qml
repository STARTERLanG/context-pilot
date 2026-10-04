import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// 设置窗：左侧导航 + 右侧内容 + 底部保存栏。
Rectangle {
    id: root
    width: 720
    height: 560
    color: theme.background

    readonly property var navItems: ["通用", "模型", "上下文", "记忆", "行为"]
    property int currentPage: 0

    // 字段标签
    component FieldLabel: Text {
        color: theme.textSecondary
        font.family: theme.fontFamily
        font.pixelSize: theme.fontSmall
        font.weight: Font.DemiBold
    }

    // ---------- 左侧导航 ----------
    Rectangle {
        id: sidebar
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 168
        color: theme.surface
        border.width: 0

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 1
            color: theme.border
        }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: theme.spaceMd
            anchors.topMargin: theme.spaceLg
            spacing: theme.spaceXs

            Text {
                text: "设置"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
                font.weight: Font.DemiBold
                leftPadding: theme.spaceMd
                bottomPadding: theme.spaceSm
            }

            Repeater {
                model: root.navItems
                delegate: Rectangle {
                    required property int index
                    required property string modelData

                    width: parent.width
                    height: 36
                    radius: theme.radiusMd
                    color: index === root.currentPage
                           ? theme.accentSoft
                           : (navHover.hovered ? theme.surfaceHover : "transparent")
                    Behavior on color { ColorAnimation { duration: 90 } }

                    Rectangle {
                        visible: index === root.currentPage
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: 3
                        height: 18
                        radius: 999
                        color: theme.accent
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: theme.spaceMd
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData
                        color: index === root.currentPage ? theme.textPrimary : theme.textSecondary
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontBody
                        font.weight: index === root.currentPage ? Font.DemiBold : Font.Normal
                    }
                    HoverHandler { id: navHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: {
                            root.currentPage = index
                            if (index === 3) settings.reloadMemories()
                        }
                    }
                }
            }
        }
    }

    // ---------- 右侧内容 ----------
    StackLayout {
        id: pages
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: saveBar.top
        anchors.margins: theme.spaceXl
        currentIndex: root.currentPage

        // ===== 通用 =====
        ColumnLayout {
            spacing: theme.spaceMd
            FieldLabel { text: "项目根目录" }
            AppTextField {
                Layout.fillWidth: true
                text: settings.projectRoot
                placeholderText: "D:/your/project · 留空则用启动时的工作目录"
                onEditingFinished: settings.projectRoot = text
            }

            Item { Layout.preferredHeight: theme.spaceXs }
            FieldLabel { text: "全局热键" }
            RowLayout {
                spacing: theme.spaceSm
                HotkeyField { id: hotkeyField; value: settings.hotkey }
                Text {
                    text: "点击后直接按下组合键"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            Item { Layout.preferredHeight: theme.spaceXs }
            FieldLabel { text: "目标 Agent" }
            AppSegmented {
                Layout.fillWidth: true
                options: ["claude", "codex", "gemini"]
                currentIndex: Math.max(0, options.indexOf(settings.agent))
                onActivated: settings.agent = options[index]
            }
            Text {
                text: "增强结果将通过剪贴板发送到所选 Agent"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
            }
            Item { Layout.fillHeight: true }
        }

        // ===== 模型 =====
        ColumnLayout {
            spacing: theme.spaceMd
            FieldLabel { text: "提供方" }
            AppSegmented {
                Layout.fillWidth: true
                options: ["stub", "openai"]
                currentIndex: settings.provider === "openai" ? 1 : 0
                onActivated: settings.provider = options[index]
            }
            Text {
                visible: settings.provider === "stub"
                text: "stub 不联网，仅用于离线验证链路。"
                color: theme.warning
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
            }

            FieldLabel { text: "接口地址（OpenAI 兼容）" }
            AppTextField {
                Layout.fillWidth: true
                text: settings.baseUrl
                onEditingFinished: settings.baseUrl = text
            }

            FieldLabel { text: "API Key" }
            AppTextField {
                Layout.fillWidth: true
                text: settings.apiKey
                echoMode: TextInput.Password
                onEditingFinished: settings.apiKey = text
            }

            RowLayout {
                spacing: theme.spaceLg
                ColumnLayout {
                    spacing: theme.spaceXs
                    FieldLabel { text: "模型名" }
                    AppTextField {
                        Layout.preferredWidth: 260
                        text: settings.model
                        onEditingFinished: settings.model = text
                    }
                }
                ColumnLayout {
                    spacing: theme.spaceXs
                    FieldLabel { text: "超时（秒）" }
                    AppSpinBox {
                        from: 5; to: 600; stepSize: 5
                        value: settings.timeout
                        onValueModified: settings.timeout = value
                    }
                }
            }
            Item { Layout.fillHeight: true }
        }

        // ===== 上下文 =====
        ColumnLayout {
            spacing: theme.spaceMd
            FieldLabel { text: "总预算 max_tokens" }
            AppSpinBox {
                from: 500; to: 100000; stepSize: 500
                value: settings.maxTokens
                onValueModified: settings.maxTokens = value
            }
            Item { Layout.preferredHeight: theme.spaceXs }
            FieldLabel { text: "三项分配" }
            GridLayout {
                columns: 2
                columnSpacing: theme.spaceLg
                rowSpacing: theme.spaceMd
                Text {
                    text: "规则"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                    Layout.alignment: Qt.AlignVCenter
                }
                AppSpinBox {
                    from: 0; to: 50000; stepSize: 100
                    value: settings.rulesTokens
                    onValueModified: settings.rulesTokens = value
                }
                Text {
                    text: "记忆"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                    Layout.alignment: Qt.AlignVCenter
                }
                AppSpinBox {
                    from: 0; to: 50000; stepSize: 100
                    value: settings.memoryTokens
                    onValueModified: settings.memoryTokens = value
                }
                Text {
                    text: "代码"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                    Layout.alignment: Qt.AlignVCenter
                }
                AppSpinBox {
                    from: 0; to: 50000; stepSize: 100
                    value: settings.codeTokens
                    onValueModified: settings.codeTokens = value
                }
            }
            Text {
                text: "三项之和不能超过总预算。"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
            }
            Item { Layout.fillHeight: true }
        }

        // ===== 记忆 =====
        ColumnLayout {
            spacing: theme.spaceMd
            RowLayout {
                Layout.fillWidth: true
                AppToggle {
                    text: "启用项目记忆"
                    checked: settings.memoryEnabled
                    onToggled: settings.memoryEnabled = checked
                }
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "刷新"
                    variant: "ghost"
                    onClicked: settings.reloadMemories()
                }
            }

            // 从对话抽取
            FieldLabel { text: "从对话抽取记忆" }
            AppTextArea {
                id: draftArea
                Layout.fillWidth: true
                Layout.preferredHeight: 90
                text: settings.draftText
                onTextChanged: settings.draftText = text
            }
            RowLayout {
                Layout.fillWidth: true
                AppButton {
                    text: "抽取候选"
                    variant: "secondary"
                    onClicked: settings.extractFromDraft()
                }
                Text {
                    text: settings.candidates.length === 0
                          ? "粘贴一段对话/结论，点「抽取候选」"
                          : "以下候选需逐条确认后入库"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                    Layout.fillWidth: true
                }
            }

            // 候选列表
            ListView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(160, settings.candidates.length * 64 + 8)
                visible: settings.candidates.length > 0
                clip: true
                model: settings.candidates
                spacing: theme.spaceSm
                delegate: Rectangle {
                    required property int index
                    required property var modelData
                    width: ListView.view.width
                    height: 58
                    radius: theme.radiusMd
                    color: theme.surface
                    border.width: 1
                    border.color: theme.border

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: theme.spaceMd
                        spacing: theme.spaceMd
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.type
                                color: theme.accent
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontCaption
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: modelData.content
                                color: theme.textPrimary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontBody
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: settings.candidateConflict(index) !== ""
                                      ? "⚠ 与已有记忆相似：" + settings.candidateConflict(index)
                                      : ""
                                visible: settings.candidateConflict(index) !== ""
                                color: theme.warning
                                font.family: theme.fontFamily
                                font.pixelSize: 10
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        AppButton {
                            text: "拒绝"
                            variant: "ghost"
                            onClicked: settings.discardCandidate(index)
                        }
                        AppButton {
                            text: "确认"
                            variant: "primary"
                            onClicked: settings.acceptCandidate(index)
                        }
                    }
                }
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: settings.memories
                spacing: theme.spaceSm
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width
                    height: 60
                    radius: theme.radiusMd
                    color: theme.surface
                    border.width: 1
                    border.color: theme.border

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: theme.spaceMd
                        spacing: theme.spaceMd
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.type + " · " + modelData.createdAt
                                color: theme.textMuted
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontCaption
                            }
                            Text {
                                text: modelData.content
                                color: theme.textPrimary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontBody
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        AppButton {
                            text: "删除"
                            variant: "ghost"
                            onClicked: settings.deleteMemory(modelData.id)
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: settings.memories.length === 0
                    text: "暂无记忆"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                }
            }
        }

        // ===== 行为 =====
        ColumnLayout {
            spacing: theme.spaceLg
            AppToggle {
                text: "开机自启"
                checked: settings.autostart
                onToggled: settings.autostart = checked
            }
            AppToggle {
                text: "点「使用」后自动写回剪贴板"
                checked: settings.autoCopy
                onToggled: settings.autoCopy = checked
            }
            AppToggle {
                text: "关闭窗口时最小化到托盘（不退出）"
                checked: settings.closeToTray
                onToggled: settings.closeToTray = checked
            }
            Item { Layout.fillHeight: true }
        }
    }

    // ---------- 底部保存栏 ----------
    Item {
        id: saveBar
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: theme.spaceXl
        anchors.topMargin: 0
        height: 44

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.top
            height: 1
            color: theme.border
        }

        Text {
            id: statusText
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            color: theme.success
            font.family: theme.fontFamily
            font.pixelSize: theme.fontSmall
        }
        AppButton {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "保存"
            variant: "primary"
            onClicked: settings.save()
        }
    }

    // ---------- 热键捕获 ----------
    component HotkeyField: Rectangle {
        id: field
        property string value: settings.hotkey
        property bool capturing: false
        implicitWidth: 220
        implicitHeight: 36
        radius: theme.radiusMd
        color: capturing ? theme.accentSoft : theme.surface
        border.width: 1
        border.color: capturing ? theme.accent : theme.border
        Behavior on border.color { ColorAnimation { duration: 100 } }
        focus: capturing

        Text {
            anchors.centerIn: parent
            text: field.capturing ? "请按下组合键…" : field.value
            color: field.capturing ? theme.accent : theme.textPrimary
            font.family: theme.fontMono
            font.pixelSize: theme.fontBody
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler {
            onTapped: {
                field.capturing = true
                field.forceActiveFocus()
            }
        }
        Keys.onPressed: function (event) {
            if (event.key === Qt.Key_Escape) {
                field.capturing = false
                event.accepted = true
                return
            }
            var captured = settings.captureHotkey(event.key, event.modifiers)
            if (captured !== "") {
                field.value = captured
                field.capturing = false
            }
            event.accepted = true
        }
        onCapturingChanged: if (capturing) forceActiveFocus()
    }

    Connections {
        target: settings
        function onSaved() { statusText.text = "已保存"; statusText.color = theme.success }
        function onSaveFailed(message) { statusText.text = message; statusText.color = theme.danger }
        function onAutostartFailed(message) { statusText.text = message; statusText.color = theme.warning }
    }
}
