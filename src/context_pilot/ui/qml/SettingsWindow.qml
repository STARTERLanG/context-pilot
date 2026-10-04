import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    width: 620
    height: 560
    color: "#17181b"

    // 供各页复用的小标题
    component SectionTitle: Text {
        color: "#8b93a1"
        font.pixelSize: 12
        font.bold: true
    }

    // 热键捕获框：点击后进入捕获态，按下组合键即录入
    component HotkeyField: Rectangle {
        id: field
        property string value: settings.hotkey
        property bool capturing: false
        width: 200
        height: 32
        radius: 6
        color: capturing ? "#2b3350" : "#21232a"
        border.color: capturing ? "#4c8dff" : "#2e3138"
        focus: capturing

        Text {
            anchors.centerIn: parent
            text: field.capturing ? "请按下组合键…" : field.value
            color: field.capturing ? "#9db4ff" : "#e8eaed"
            font.pixelSize: 13
        }
        MouseArea {
            anchors.fill: parent
            onClicked: {
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "设置"
            color: "#e8eaed"
            font.pixelSize: 20
            font.bold: true
        }

        TabBar {
            id: tabs
            Layout.fillWidth: true
            TabButton { text: "通用" }
            TabButton { text: "模型" }
            TabButton { text: "上下文" }
            TabButton { text: "记忆" }
            TabButton { text: "行为" }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // ---------- 通用 ----------
            ScrollView {
                ColumnLayout {
                    width: parent.width
                    spacing: 10
                    SectionTitle { text: "项目根目录（留空则用启动时的工作目录）" }
                    TextField {
                        Layout.fillWidth: true
                        text: settings.projectRoot
                        placeholderText: "D:/your/project"
                        onEditingFinished: settings.projectRoot = text
                    }
                    SectionTitle { text: "全局热键（点击后按下组合键）" }
                    HotkeyField { value: settings.hotkey }
                }
            }

            // ---------- 模型 ----------
            ScrollView {
                ColumnLayout {
                    width: parent.width
                    spacing: 10
                    SectionTitle { text: "提供方" }
                    ComboBox {
                        Layout.fillWidth: true
                        model: ["stub", "openai"]
                        currentIndex: settings.provider === "openai" ? 1 : 0
                        onActivated: settings.provider = currentText
                    }
                    Text {
                        visible: settings.provider === "stub"
                        text: "stub 不联网，仅用于离线验证链路。"
                        color: "#c9a227"
                        font.pixelSize: 12
                    }
                    SectionTitle { text: "接口地址（OpenAI 兼容）" }
                    TextField {
                        Layout.fillWidth: true
                        text: settings.baseUrl
                        onEditingFinished: settings.baseUrl = text
                    }
                    SectionTitle { text: "API Key" }
                    TextField {
                        Layout.fillWidth: true
                        text: settings.apiKey
                        echoMode: TextInput.Password
                        onEditingFinished: settings.apiKey = text
                    }
                    SectionTitle { text: "模型名" }
                    TextField {
                        Layout.fillWidth: true
                        text: settings.model
                        onEditingFinished: settings.model = text
                    }
                    SectionTitle { text: "超时（秒）" }
                    SpinBox {
                        from: 5; to: 600; stepSize: 5
                        value: settings.timeout
                        onValueModified: settings.timeout = value
                    }
                }
            }

            // ---------- 上下文 ----------
            ScrollView {
                ColumnLayout {
                    width: parent.width
                    spacing: 10
                    SectionTitle { text: "总预算 max_tokens" }
                    SpinBox {
                        from: 500; to: 100000; stepSize: 500
                        value: settings.maxTokens
                        onValueModified: settings.maxTokens = value
                    }
                    SectionTitle { text: "规则预算" }
                    SpinBox {
                        from: 0; to: 50000; stepSize: 100
                        value: settings.rulesTokens
                        onValueModified: settings.rulesTokens = value
                    }
                    SectionTitle { text: "记忆预算" }
                    SpinBox {
                        from: 0; to: 50000; stepSize: 100
                        value: settings.memoryTokens
                        onValueModified: settings.memoryTokens = value
                    }
                    SectionTitle { text: "代码预算" }
                    SpinBox {
                        from: 0; to: 50000; stepSize: 100
                        value: settings.codeTokens
                        onValueModified: settings.codeTokens = value
                    }
                    Text {
                        text: "三项预算之和不能超过总预算。"
                        color: "#8b93a1"
                        font.pixelSize: 12
                    }
                }
            }

            // ---------- 记忆 ----------
            ColumnLayout {
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    CheckBox {
                        text: "启用项目记忆"
                        checked: settings.memoryEnabled
                        onToggled: settings.memoryEnabled = checked
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "刷新"
                        onClicked: settings.reloadMemories()
                    }
                }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: settings.memories
                    spacing: 6
                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 62
                        radius: 6
                        color: "#21232a"
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: modelData.type + " · " + modelData.createdAt
                                    color: "#8b93a1"
                                    font.pixelSize: 11
                                }
                                Text {
                                    text: modelData.content
                                    color: "#e8eaed"
                                    font.pixelSize: 13
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                            Button {
                                text: "删除"
                                onClicked: settings.deleteMemory(modelData.id)
                            }
                        }
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: settings.memories.length === 0
                        text: "暂无记忆"
                        color: "#5c636e"
                    }
                }
            }

            // ---------- 行为 ----------
            ScrollView {
                ColumnLayout {
                    width: parent.width
                    spacing: 12
                    CheckBox {
                        text: "开机自启"
                        checked: settings.autostart
                        onToggled: settings.autostart = checked
                    }
                    CheckBox {
                        text: "点「使用」后自动写回剪贴板"
                        checked: settings.autoCopy
                        onToggled: settings.autoCopy = checked
                    }
                    CheckBox {
                        text: "关闭窗口时最小化到托盘（不退出）"
                        checked: settings.closeToTray
                        onToggled: settings.closeToTray = checked
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                id: statusText
                color: "#7ec17e"
                font.pixelSize: 12
                Layout.fillWidth: true
            }
            Button {
                text: "保存"
                highlighted: true
                onClicked: settings.save()
            }
        }
    }

    Connections {
        target: settings
        function onSaved() { statusText.text = "已保存" }
        function onSaveFailed(message) { statusText.text = message; statusText.color = "#e06c75" }
        function onAutostartFailed(message) { statusText.text = message; statusText.color = "#e06c75" }
    }
}
