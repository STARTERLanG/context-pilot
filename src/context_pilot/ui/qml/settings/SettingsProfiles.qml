import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「模型配置」：多套 OpenAI 兼容配置。新增表单 + 列表（删除模式 / 展开编辑）。
//
// 数据来自 settingsCtl.profiles（每项含脱敏 key）。编辑区的 API Key 默认展示
// 掩码值，只有点「查看」才回填明文；未编辑过则不参与保存，避免用掩码覆盖真密钥。
Flickable {
    id: root
    contentWidth: width
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    // 页面级状态：切到别的分类再回来仍保持（分区 Item 不销毁）
    property bool deleteMode: false
    property string expandedId: ""
    property string testingId: ""
    property var models: []
    property bool fetching: false
    property bool keyVisible: false
    // 已生效条数（供标题行总览；随列表刷新自动重算）
    readonly property int enabledCount: {
        var count = 0
        for (var i = 0; i < settingsCtl.profiles.length; i++) {
            if (settingsCtl.profiles[i].enabled) count++
        }
        return count
    }

    Connections {
        target: settingsCtl
        function onModelsFetched(list) {
            root.models = list
            root.fetching = false
            modelCombo.currentText = list.length > 0 ? list[0] : ""
        }
        function onProfileTested(profileId, ok, detail) {
            root.testingId = ""
        }
    }

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
                    text: "新增模型配置"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: "多套 OpenAI 兼容配置。下方列表中可勾选任意多条使其生效；"
                          + "增强时再在主页面的「模型」下拉中指定本次使用哪一条"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    wrapMode: Text.Wrap
                }
            }

            AppFormRow {
                Layout.fillWidth: true
                label: "配置名称"
                AppTextField {
                    id: nameField
                    anchors.centerIn: parent
                    width: parent.width
                    placeholderText: "例如：OpenAI 主力"
                }
            }

            AppFormRow {
                Layout.fillWidth: true
                label: "Base URL"
                AppTextField {
                    id: baseField
                    anchors.centerIn: parent
                    width: parent.width
                    placeholderText: "https://api.openai.com/v1"
                }
            }

            // API Key：密码回显 + 显示/隐藏（只切回显模式，不改内容）
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceMd
                Text {
                    Layout.preferredWidth: 96
                    Layout.alignment: Qt.AlignVCenter
                    text: "API Key"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    horizontalAlignment: Text.AlignRight
                }
                AppTextField {
                    id: keyField
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    echoMode: root.keyVisible ? TextInput.Normal : TextInput.Password
                    placeholderText: "sk-…（保存后仅以掩码形式展示）"
                }
                AppButton {
                    text: root.keyVisible ? "隐藏" : "显示"
                    variant: "secondary"
                    Layout.preferredWidth: 64
                    Layout.preferredHeight: 36
                    onClicked: root.keyVisible = !root.keyVisible
                }
            }

            // 模型：先拉取远端列表再选择
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceMd
                Text {
                    Layout.preferredWidth: 96
                    Layout.alignment: Qt.AlignVCenter
                    text: "模型"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    horizontalAlignment: Text.AlignRight
                }
                AppComboBox {
                    id: modelCombo
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    model: root.models
                }
                AppButton {
                    id: fetchBtn
                    text: root.fetching ? "获取中…" : "获取模型"
                    variant: "primary"
                    enabled: !root.fetching
                    Layout.preferredWidth: 96
                    Layout.preferredHeight: 36
                    onClicked: {
                        root.fetching = true
                        settingsCtl.fetchModels(baseField.text, keyField.text)
                    }
                }
            }

            // 校验提示由控制层统一写入页面底部保存栏，这里只铺满留白 + 放「新增」
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "新增"
                    variant: "primary"
                    Layout.preferredWidth: 88
                    Layout.preferredHeight: 36
                    onClicked: {
                        if (settingsCtl.addProfile(
                                nameField.text, baseField.text, keyField.text,
                                modelCombo.currentText)) {
                            nameField.text = ""
                            baseField.text = ""
                            keyField.text = ""
                            root.keyVisible = false
                            root.models = []
                            modelCombo.currentText = ""
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
                    text: "已添加模型"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                // 生效数量总览：多条同时生效是常态，这里给出一个可核对的数字
                Text {
                    visible: settingsCtl.profiles.length > 0
                    text: "已生效 " + root.enabledCount + " / " + settingsCtl.profiles.length
                    color: root.enabledCount > 0 ? theme.accent : theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
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
                visible: settingsCtl.profiles.length === 0
                text: "暂无模型配置，请在上方添加"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
                horizontalAlignment: Text.AlignHCenter
            }

            Repeater {
                model: settingsCtl.profiles
                delegate: ColumnLayout {
                    id: item
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: theme.spaceSm

                    // 条目本地状态（列表刷新即重建，故不需要手动复位）
                    property bool expanded: root.expandedId === modelData.id
                    property bool keyRevealed: false
                    property bool keyEdited: false

                    // ---- 主行：状态条 + 名称·模型 + 生效标记 + 操作 + 启用开关 ----
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spaceSm

                        // 左侧状态条：已生效用强调色实心，未生效留空描边。
                        // 与右侧文字标签共同构成「已生效 / 未生效」的双重提示，
                        // 扫一眼列表就能分辨，不必逐个去读开关位置。
                        Rectangle {
                            Layout.alignment: Qt.AlignVCenter
                            Layout.preferredWidth: 3
                            Layout.preferredHeight: 18
                            radius: 1.5
                            color: modelData.enabled ? theme.accent : "transparent"
                            border.width: modelData.enabled ? 0 : 1
                            border.color: theme.borderStrong
                        }

                        Text {
                            Layout.fillWidth: true
                            text: modelData.name + "  ·  " + modelData.model
                            color: modelData.enabled ? theme.textPrimary : theme.textSecondary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSmall
                            elide: Text.ElideRight
                        }

                        // 状态标签：两种状态都显式标注（未生效不再靠「没有标签」暗示）
                        Rectangle {
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 18
                            radius: theme.radiusFull
                            color: modelData.enabled ? theme.accentSoft : theme.surfaceActive
                            Text {
                                anchors.centerIn: parent
                                text: modelData.enabled ? "已生效" : "未生效"
                                color: modelData.enabled ? theme.accent : theme.textSecondary
                                font.family: theme.fontFamily
                                font.pixelSize: 10
                            }
                        }

                        AppButton {
                            text: root.testingId === modelData.id ? "测试中…" : "测试"
                            variant: "secondary"
                            enabled: root.testingId === ""
                            Layout.preferredWidth: 68
                            Layout.preferredHeight: 30
                            onClicked: {
                                root.testingId = modelData.id
                                settingsCtl.testProfile(modelData.id)
                            }
                        }

                        AppButton {
                            visible: root.deleteMode
                            text: "删除"
                            variant: "danger"
                            Layout.preferredWidth: 60
                            Layout.preferredHeight: 30
                            onClicked: settingsCtl.deleteProfile(modelData.id)
                        }

                        AppToggle {
                            Layout.alignment: Qt.AlignVCenter
                            checked: modelData.enabled
                            onToggled: (checked) => settingsCtl.setProfileEnabled(modelData.id, checked)
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
                            label: "配置名称"
                            AppTextField {
                                id: itemName
                                anchors.centerIn: parent
                                width: parent.width
                                text: modelData.name
                            }
                        }

                        AppFormRow {
                            Layout.fillWidth: true
                            label: "Base URL"
                            AppTextField {
                                id: itemBase
                                anchors.centerIn: parent
                                width: parent.width
                                text: modelData.baseUrl
                            }
                        }

                        AppFormRow {
                            Layout.fillWidth: true
                            label: "模型"
                            AppTextField {
                                id: itemModel
                                anchors.centerIn: parent
                                width: parent.width
                                text: modelData.model
                            }
                        }

                        // Key：默认掩码；「查看」回填明文；未编辑则不写回
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.spaceMd
                            Text {
                                Layout.preferredWidth: 96
                                Layout.alignment: Qt.AlignVCenter
                                text: "API Key"
                                color: theme.textSecondary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontSmall
                                horizontalAlignment: Text.AlignRight
                            }
                            AppTextField {
                                id: itemKey
                                Layout.fillWidth: true
                                Layout.preferredHeight: 36
                                text: modelData.apiKey
                                placeholderText: "保持掩码值表示不修改"
                                onTextEdited: item.keyEdited = true
                            }
                            AppButton {
                                text: item.keyRevealed ? "隐藏" : "查看"
                                variant: "secondary"
                                Layout.preferredWidth: 64
                                Layout.preferredHeight: 36
                                onClicked: {
                                    if (item.keyRevealed) {
                                        itemKey.text = modelData.apiKey
                                        item.keyRevealed = false
                                        item.keyEdited = false
                                    } else {
                                        itemKey.text = settingsCtl.revealKey(modelData.id)
                                        item.keyRevealed = true
                                        item.keyEdited = true
                                    }
                                }
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
                                    if (settingsCtl.updateProfile(
                                            modelData.id, itemName.text, itemBase.text,
                                            itemModel.text, itemKey.text, item.keyEdited)) {
                                        root.expandedId = ""
                                    }
                                }
                            }
                        }
                    }

                    // 条目分隔线
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
