import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 记忆管理：分「项目记忆」与「全局记忆」两栏。
// 两类物理隔离（项目按目录哈希建库、全局单独一库），界面用不同标签色区分：
// 项目记忆 teal、全局记忆 amber。
//
// 布局约定（修复重叠 / 层级混乱）：
// - 卡片用「有自身高度的 ColumnLayout」直接作 Repeater delegate，不再用
//   Rectangle + anchors.fill 的空壳（父级高度为 0 会让所有卡片叠在一起）；
// - 新增 / 编辑统一走顶层 Popup（overlay 层），不嵌在 Flickable 内——下拉框
//   不会被 Flickable 的 clip 裁掉，也不会被相邻卡片盖住；
// - 所有写操作由 memoryManageCtl 完成后刷新 Property，QML 绑定自动更新展示。
Item {
    id: root
    objectName: "settingsMemory"

    property string scope: "project"       // 当前展示哪一类：project / global
    property string editingId: ""          // 正在编辑的记忆 id（空=新增）
    property string editingContent: ""
    property string editingType: ""

    // 供集成测试读取卡片几何：QML 侧直接拿到 Repeater 的 delegate，
    // 绕开 PySide6 对 Repeater 子项 objectName 的包装差异。
    function cardGeometry() {
        var result = []
        for (var i = 0; i < memoryRepeater.count; i++) {
            var item = memoryRepeater.itemAt(i)
            result.push({ y: item.y, height: item.height })
        }
        return result
    }

    // 供集成测试真正打开编辑弹窗（Popup 的 visible 赋值不走 open 流程）
    function openEditorForTest() {
        root.editingId = ""
        root.editingContent = ""
        root.editingType = "项目事实"
        editorPopup.open()
    }

    // 供集成测试断言高度：工具栏被误设 fillHeight 时曾膨胀到整页高度
    function toolbarHeight() {
        return toolbarLayout.height
    }

    function editorHeight() {
        return editorPopup.height
    }

    // ---------- 主布局：说明 / 工具栏 / 列表 ----------
    ColumnLayout {
        objectName: "mainCol"
        anchors.fill: parent
        // 与其他设置子页保持同一内边距，避免卡片紧贴窗口边缘
        anchors.margins: theme.spaceLg
        spacing: theme.spaceSm

        Text {
            Layout.fillWidth: true
            text: "记忆是跨会话保留的长期知识，增强时会自动带入。项目记忆仅对选定项目生效；全局记忆对所有项目生效。"
            color: theme.textSecondary
            font.family: theme.fontFamily
            font.pixelSize: theme.fontSmall
            wrapMode: Text.WordWrap
        }

        // ---------- 工具栏：两类切换 + 项目选择 + 新增 ----------
        // 高度必须锁死：子项若用 Layout.fillHeight，RowLayout 的隐式高度会被
        // 撑到父级可用高度（实测 519px），把下方列表挤成 0 高。
        RowLayout {
            id: toolbarLayout
            objectName: "toolbar"
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            Layout.minimumHeight: 36
            Layout.maximumHeight: 36
            spacing: theme.spaceSm

            Rectangle {
                Layout.preferredWidth: 112
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignVCenter
                radius: theme.radiusFull
                color: root.scope === "project" ? theme.accent : theme.surface
                border.width: root.scope === "project" ? 0 : 1
                border.color: theme.border
                Text {
                    anchors.centerIn: parent
                    text: "项目记忆 · " + memoryManageCtl.projectMemories.length
                    color: root.scope === "project" ? theme.textInverse : theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                }
                TapHandler {
                    onTapped: {
                        root.scope = "project"
                        root.editingId = ""
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: 112
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignVCenter
                radius: theme.radiusFull
                color: root.scope === "global" ? theme.warning : theme.surface
                border.width: root.scope === "global" ? 0 : 1
                border.color: theme.border
                Text {
                    anchors.centerIn: parent
                    text: "全局记忆 · " + memoryManageCtl.globalMemories.length
                    color: root.scope === "global" ? theme.textInverse : theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                }
                TapHandler {
                    onTapped: {
                        root.scope = "global"
                        root.editingId = ""
                    }
                }
            }

            // 仅项目记忆显示：按项目查看，不混合展示所有项目
            Text {
                visible: root.scope === "project"
                Layout.alignment: Qt.AlignVCenter
                text: "查看项目"
                color: theme.textSecondary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSmall
            }
            AppComboBox {
                id: projectCombo
                visible: root.scope === "project"
                Layout.preferredWidth: 160
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignVCenter
                model: memoryManageCtl.projects
                placeholder: "无项目"
                currentText: memoryManageCtl.selectedProject
                onActivated: memoryManageCtl.selectProjectByName(text)
            }

            Item { Layout.fillWidth: true }
            AppButton {
                text: "新增"
                variant: "primary"
                Layout.preferredWidth: 72
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignVCenter
                onClicked: {
                    root.editingId = ""
                    root.editingContent = ""
                    root.editingType = "项目事实"
                    editorPopup.open()
                }
            }
        }

        // ---------- 列表（卡片高度由内容撑开，互不重叠） ----------
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: width
            contentHeight: listCol.implicitHeight
            boundsBehavior: Flickable.StopAtBounds

            ColumnLayout {
                id: listCol
                width: parent.width
                spacing: theme.spaceSm

                Text {
                    Layout.fillWidth: true
                    visible: (root.scope === "project"
                             ? memoryManageCtl.projectMemories.length
                             : memoryManageCtl.globalMemories.length) === 0
                    text: root.scope === "project"
                          ? "该项目暂无记忆。可在增强后确认候选，或点「新增」手动添加。"
                          : "暂无全局记忆。点「新增」添加对所有项目生效的偏好或约定。"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    id: memoryRepeater
                    objectName: "memoryRepeater"
                    model: root.scope === "project"
                           ? memoryManageCtl.projectMemories
                           : memoryManageCtl.globalMemories
                    // 卡片用 Rectangle 作根，高度显式绑定内容 implicitHeight + 内边距。
                    // 原实现是空壳 Rectangle + 内部 anchors.fill 的 ColumnLayout，
                    // 父级高度为 0 导致所有卡片叠在一起——这里由内容撑开，互不覆盖。
                    delegate: Rectangle {
                        objectName: "memoryCard"
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: innerCol.implicitHeight + theme.spaceMd * 2
                        radius: theme.radiusMd
                        color: theme.surfaceHover
                        border.width: 1
                        border.color: theme.border

                        ColumnLayout {
                            id: innerCol
                            anchors.fill: parent
                            anchors.margins: theme.spaceMd
                            spacing: theme.spaceSm

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: theme.spaceSm

                                Rectangle {
                                    Layout.preferredWidth: typeText.implicitWidth + 16
                                    Layout.preferredHeight: 20
                                    radius: theme.radiusFull
                                    color: root.scope === "project" ? theme.accentSoft : theme.warning
                                    Text {
                                        id: typeText
                                        anchors.centerIn: parent
                                        text: modelData.type
                                        color: root.scope === "project" ? theme.accent : theme.textInverse
                                        font.family: theme.fontFamily
                                        font.pixelSize: 10
                                    }
                                }
                                Rectangle {
                                    Layout.preferredWidth: scopeText.implicitWidth + 16
                                    Layout.preferredHeight: 20
                                    radius: theme.radiusFull
                                    color: theme.surfaceActive
                                    Text {
                                        id: scopeText
                                        anchors.centerIn: parent
                                        text: root.scope === "project" ? "仅本项目" : "所有项目"
                                        color: theme.textSecondary
                                        font.family: theme.fontFamily
                                        font.pixelSize: 10
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                AppButton {
                                    text: "编辑"
                                    variant: "ghost"
                                    Layout.preferredWidth: 56
                                    Layout.preferredHeight: 28
                                    onClicked: {
                                        root.editingId = modelData.id
                                        root.editingContent = modelData.content
                                        root.editingType = modelData.type
                                        editorPopup.open()
                                    }
                                }
                                AppButton {
                                    text: "删除"
                                    variant: "danger"
                                    Layout.preferredWidth: 56
                                    Layout.preferredHeight: 28
                                    onClicked: memoryManageCtl.delete(root.scope, modelData.id)
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.content
                                color: theme.textPrimary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontSmall
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: memoryManageCtl.error
            visible: memoryManageCtl.error.length > 0
            color: theme.danger
            font.family: theme.fontFamily
            font.pixelSize: theme.fontCaption
            wrapMode: Text.WordWrap
        }
    }

    // ---------- 新增 / 编辑弹窗：顶层 overlay，不受 Flickable 裁剪 ----------
    Popup {
        id: editorPopup
        anchors.centerIn: parent
        width: Math.min(root.width - 80, 480)
        // 高度随内容走：固定值会在控件少时留大片空白、控件多时挤压。
        height: editorCol.implicitHeight + padding * 2
        padding: theme.spaceLg
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: theme.radiusLg
            color: theme.surface
            border.width: 1
            border.color: theme.border
        }

        contentItem: ColumnLayout {
            id: editorCol
            spacing: theme.spaceMd

            Text {
                Layout.fillWidth: true
                text: root.editingId.length > 0 ? "编辑记忆" : "新增记忆"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }

            AppFormRow {
                Layout.fillWidth: true
                label: "类型"
                // AppFormRow 的 controlBox 是普通 Item，子控件必须显式铺满，
                // 否则 AppTextField 宽度为 0、完全不可见。
                AppComboBox {
                    id: editorType
                    anchors.fill: parent
                    model: ["项目事实", "架构决策", "用户偏好", "历史结论"]
                    currentText: root.editingType
                }
            }
            AppFormRow {
                Layout.fillWidth: true
                label: "内容"
                AppTextField {
                    id: editorContent
                    anchors.fill: parent
                    text: root.editingContent
                    placeholderText: "例如：必须使用 FastAPI，不要直连数据库"
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: theme.spaceXs
                spacing: theme.spaceSm
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "取消"
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 32
                    onClicked: editorPopup.close()
                }
                AppButton {
                    text: "保存"
                    variant: "primary"
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 32
                    onClicked: {
                        var text = editorContent.text
                        if (text.trim().length === 0) return
                        if (root.editingId.length > 0) {
                            memoryManageCtl.update(root.scope, root.editingId,
                                                   text, editorType.currentText)
                        } else {
                            memoryManageCtl.add(root.scope, text, editorType.currentText)
                        }
                        editorPopup.close()
                    }
                }
            }
        }
    }
}
