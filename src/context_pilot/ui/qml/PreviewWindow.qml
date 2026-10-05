import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// 预览窗：顶栏（含窗口控制按钮）+ 原始指令 + 三视图切换 + Token 统计 + 底部操作栏。
// 无边框窗口，外观全部自绘：外层透明留出阴影，内层圆角白卡承载内容，
// 顶栏右侧为最小化/最大化/关闭按钮（经 windowCtl 调用原生 API）。
Rectangle {
    id: root
    // 752×712 = 卡片可视 720×680 + 四周阴影边距 2×16；卡片内容宽与既定 720 一致
    width: 752
    height: 712
    color: "transparent"

    readonly property var views: ["增强结果", "差异", "上下文"]
    property int currentView: 0
    property real promptHeight: 200  // 原始指令区默认高度（约 8 行文本）

    // 阴影边距：卡片与窗口边缘之间为阴影留出的空间
    readonly property int shadowMargin: 16
    readonly property int cardRadius: 14
    // 最大化时无缝铺满：边距/圆角归零、阴影隐藏
    readonly property bool maxed: windowCtl.isMaximized

    // ---------- 阴影（多层半透明圆角矩形，越靠外越淡）----------
    Rectangle {
        anchors.fill: card
        anchors.margins: -6
        radius: root.cardRadius + 6
        color: "#0A000000"
        opacity: root.maxed ? 0 : 1
    }
    Rectangle {
        anchors.fill: card
        anchors.margins: -4
        radius: root.cardRadius + 4
        color: "#0E000000"
        opacity: root.maxed ? 0 : 1
    }
    Rectangle {
        anchors.fill: card
        anchors.margins: -2
        radius: root.cardRadius + 2
        color: "#16000000"
        opacity: root.maxed ? 0 : 1
    }

    // ---------- 主卡片（圆角，承载全部内容）----------
    Rectangle {
        id: card
        anchors.fill: parent
        anchors.margins: root.maxed ? 0 : root.shadowMargin
        radius: root.maxed ? 0 : root.cardRadius
        color: theme.background
        clip: true
        Behavior on anchors.margins { NumberAnimation { duration: 120 } }

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

                // 应用图标：纸飞机（与托盘/任务栏图标一致）
                Rectangle {
                    width: 26; height: 26; radius: theme.radiusSm
                    color: theme.accent
                    anchors.verticalCenter: parent.verticalCenter
                    Canvas {
                        anchors.fill: parent
                        anchors.margins: 4
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            ctx.fillStyle = theme.textInverse
                            ctx.beginPath()
                            ctx.moveTo(width, height * 0.06)
                            ctx.lineTo(width * 0.65, height)
                            ctx.lineTo(width * 0.5, height * 0.56)
                            ctx.lineTo(width * 0.06, height * 0.4)
                            ctx.closePath()
                            ctx.fill()
                        }
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

            // 右侧：窗口控制按钮（最小化 / 最大化 / 关闭）
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: theme.spaceXs

                // 最小化
                Rectangle {
                    id: minBtn
                    objectName: "minBtn"
                    width: 34; height: 30
                    radius: theme.radiusSm
                    color: minHover.hovered ? theme.surfaceHover : "transparent"
                    anchors.verticalCenter: parent.verticalCenter
                    Canvas {
                        width: 14; height: 14
                        anchors.centerIn: parent
                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)
                            c.strokeStyle = theme.textSecondary
                            c.lineWidth = 1.4
                            c.lineCap = "round"
                            c.beginPath()
                            c.moveTo(2, height / 2)
                            c.lineTo(width - 2, height / 2)
                            c.stroke()
                        }
                    }
                    HoverHandler { id: minHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: windowCtl.minimize() }
                }
                // 最大化 / 还原
                Rectangle {
                    id: maxBtn
                    objectName: "maxBtn"
                    width: 34; height: 30
                    radius: theme.radiusSm
                    color: maxHover.hovered ? theme.surfaceHover : "transparent"
                    anchors.verticalCenter: parent.verticalCenter
                    Canvas {
                        width: 14; height: 14
                        anchors.centerIn: parent
                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)
                            c.strokeStyle = theme.textSecondary
                            c.lineWidth = 1.4
                            c.strokeRect(2, 2, width - 4, height - 4)
                        }
                    }
                    HoverHandler { id: maxHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: windowCtl.toggleMaximize() }
                }
                // 关闭
                Rectangle {
                    id: closeBtn
                    objectName: "closeBtn"
                    width: 34; height: 30
                    radius: theme.radiusSm
                    color: closeHover.hovered ? "#DC2626" : "transparent"
                    anchors.verticalCenter: parent.verticalCenter
                    Canvas {
                        width: 14; height: 14
                        anchors.centerIn: parent
                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)
                            c.strokeStyle = closeHover.hovered ? theme.textInverse : theme.textSecondary
                            c.lineWidth = 1.4
                            c.lineCap = "round"
                            c.beginPath()
                            c.moveTo(2.5, 2.5)
                            c.lineTo(width - 2.5, height - 2.5)
                            c.moveTo(width - 2.5, 2.5)
                            c.lineTo(2.5, height - 2.5)
                            c.stroke()
                        }
                    }
                    HoverHandler { id: closeHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: windowCtl.close() }
                }
            }

            // 无边框拖动区：覆盖顶栏空白（按钮在上层，会优先响应点击）
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                z: -1
                onPressed: windowCtl.startMove()
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

            // 原始指令（标题在左，历史记录按钮在右）
            // 注意：必须用 RowLayout——普通 Row 中 Layout.fillWidth 附加属性
            // 无效，弹簧不会拉伸，按钮无法推到右侧。
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceSm
                Text {
                    Layout.alignment: Qt.AlignVCenter
                    text: "原始指令"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }

                // 历史记录（图标 + 文字胶囊）
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    width: historyContent.width + theme.spaceMd
                    height: 24
                    radius: theme.radiusFull
                    color: historyHover.hovered ? theme.surfaceActive : theme.surface
                    border.width: 1
                    border.color: theme.border
                    Row {
                        id: historyContent
                        anchors.centerIn: parent
                        spacing: theme.spaceXs
                        // 时钟图标
                        Canvas {
                            width: 12; height: 12
                            anchors.verticalCenter: parent.verticalCenter
                            onPaint: {
                                var c = getContext("2d")
                                c.clearRect(0, 0, width, height)
                                c.strokeStyle = theme.textSecondary
                                c.lineWidth = 1.2
                                c.beginPath()
                                c.arc(width / 2, height / 2, width / 2 - 1, 0, Math.PI * 2)
                                c.moveTo(width / 2, height / 2)
                                c.lineTo(width / 2, height / 2 - (height / 2 - 2))
                                c.moveTo(width / 2, height / 2)
                                c.lineTo(width / 2 + (width / 2 - 2), height / 2 + 1)
                                c.stroke()
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "历史记录 (" + preview.history.length + ")"
                            color: theme.textSecondary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                        }
                    }
                    HoverHandler { id: historyHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: historyPopup.open() }
                }
            }

            // 原始指令输入区：默认约 8 行，底部手柄可拖拽调整高度（44~280）
            AppCard {
                id: promptCard
                Layout.fillWidth: true
                Layout.preferredHeight: promptHeight
                Layout.minimumHeight: 44
                Layout.maximumHeight: 280
                padding: theme.spaceMd
                AppTextArea {
                    id: promptArea
                    anchors.fill: parent
                    readOnly: false
                    // 可编辑：单向初始化，避免与只读 Property 双向绑定导致输入被覆盖
                    text: ""
                    Component.onCompleted: promptArea.text = preview.originalPrompt
                }
                // 热键触发新增强会话（begin 用剪贴板内容覆盖 originalPrompt）时，
                // 同步刷新输入框；用户手动编辑不受影响（编辑不触发模型 changed）。
                Connections {
                    target: preview
                    function onChanged() {
                        promptArea.text = preview.originalPrompt
                    }
                }
                // 拖拽手柄：悬浮于底部，上下拖动改变高度
                Rectangle {
                    id: resizeHandle
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 6
                    color: "transparent"
                    Rectangle {
                        anchors.centerIn: parent
                        width: 32
                        height: 3
                        radius: 1.5
                        color: theme.borderStrong
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.SizeVerCursor
                        property real startY: 0
                        property real startHeight: 0
                        onPressed: {
                            startY = mouseY
                            startHeight = promptCard.height
                        }
                        onPositionChanged: {
                            var dh = mouseY - startY
                            promptHeight = Math.max(44, Math.min(280, startHeight + dh))
                        }
                    }
                }
            }

            // 视图切换 + 清空按钮（清空在分段器右侧，即两个输入区之间的主页面中间偏右）
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceMd

                AppSegmented {
                    Layout.fillWidth: false
                    options: root.views
                    currentIndex: root.currentView
                    onActivated: (index) => root.currentView = index
                }

                Item { Layout.fillWidth: true }

                // 清空按钮（图标 + 文字胶囊，同时清空原始指令与增强结果两个输入框）
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    width: clearContent.width + theme.spaceMd
                    height: 24
                    radius: theme.radiusFull
                    color: clearHover.hovered ? theme.surfaceActive : theme.surface
                    border.width: 1
                    border.color: theme.border
                    Row {
                        id: clearContent
                        anchors.centerIn: parent
                        spacing: theme.spaceXs
                        // 垃圾桶图标
                        Canvas {
                            width: 12; height: 12
                            anchors.verticalCenter: parent.verticalCenter
                            onPaint: {
                                var c = getContext("2d")
                                c.clearRect(0, 0, width, height)
                                c.strokeStyle = theme.textSecondary
                                c.lineWidth = 1.2
                                // 桶身
                                c.strokeRect(2.5, 4, 7, 6.5)
                                // 桶盖
                                c.beginPath()
                                c.moveTo(1.5, 3)
                                c.lineTo(10.5, 3)
                                c.stroke()
                                // 提手
                                c.beginPath()
                                c.moveTo(4.5, 1.5)
                                c.lineTo(7.5, 1.5)
                                c.stroke()
                                // 竖纹
                                c.beginPath()
                                c.moveTo(5, 5.5)
                                c.lineTo(5, 9)
                                c.moveTo(7, 5.5)
                                c.lineTo(7, 9)
                                c.stroke()
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "清空"
                            color: theme.textSecondary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                        }
                    }
                    HoverHandler { id: clearHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: {
                            promptArea.text = ""
                            enhancedArea.text = ""
                        }
                    }
                }
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
                    color: modelData.kind === "added" ? "#ECFDF5"
                         : modelData.kind === "removed" ? "#FEF2F2"
                         : "transparent"

                    Row {
                        anchors.fill: parent
                        anchors.leftMargin: theme.spaceMd
                        spacing: theme.spaceMd
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 30
                            text: modelData.oldLine ?? ""
                            color: theme.textMuted
                            font.family: theme.fontMono
                            font.pixelSize: theme.fontCaption
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 30
                            text: modelData.newLine ?? ""
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

            // 状态点 + 状态文字 + Token 统计（原顶栏状态胶囊语义不变，位置弱化）
            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: theme.spaceSm
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7; height: 7; radius: 999
                    color: preview.status.indexOf("失败") === 0 ? theme.danger
                         : preview.status === "完成" ? theme.success
                         : theme.warning
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: preview.status
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "· 原始 " + preview.tokenStats.original
                        + " · 上下文 " + preview.tokenStats.context
                        + " · 增强 " + preview.tokenStats.enhanced
                        + " · 合计 " + preview.tokenStats.total
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                }
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: theme.spaceSm
                AppButton {
                    text: "发送到 Agent"
                    variant: "secondary"
                    onClicked: preview.sendToAgent(enhancedArea.text)
                }
                AppButton {
                    text: "使用增强 Prompt"
                    variant: "primary"
                    onClicked: preview.use(enhancedArea.text)
                }
            }
        }
    }

    // ---------- 历史记录弹窗 ----------
    Popup {
        id: historyPopup
        objectName: "historyPopup"
        x: (card.width - width) / 2
        y: (card.height - height) / 2
        width: Math.min(card.width - 80, 520)
        height: Math.min(card.height - 80, 440)
        padding: theme.spaceLg
        modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: theme.radiusLg
            color: theme.surface
            border.width: 1
            border.color: theme.border
        }

        contentItem: ColumnLayout {
            id: historyPanel
            spacing: theme.spaceMd

            // 当前展开的历史条目 index（-1 表示全部收起）
            property int expandedIndex: -1

            Row {
                Layout.fillWidth: true
                Text {
                    text: "历史优化记录"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    width: 26; height: 26; radius: theme.radiusSm
                    color: closePopHover.hovered ? theme.surfaceHover : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        color: theme.textSecondary
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontBody
                    }
                    HoverHandler { id: closePopHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: historyPopup.close() }
                }
            }

            // 空态
            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: preview.history.length === 0
                text: "暂无历史记录"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            // 历史列表：每条记录独立条目，点击展开查看原始指令与增强结果
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: preview.history.length > 0
                clip: true
                model: preview.history
                spacing: theme.spaceSm

                delegate: Rectangle {
                    id: item
                    required property var modelData
                    required property int index
                    property bool expanded: historyPanel.expandedIndex === index

                    width: ListView.view.width
                    height: expanded ? itemColumn.height + theme.spaceMd * 2
                                     : headerRow.height + theme.spaceMd * 2
                    radius: theme.radiusMd
                    color: expanded ? theme.surfaceActive : theme.background
                    border.width: 1
                    border.color: expanded ? theme.borderStrong : theme.border
                    Behavior on height { NumberAnimation { duration: 120 } }

                    // 收起态：时间 + 原始指令摘要（单行）
                    Row {
                        id: headerRow
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.leftMargin: theme.spaceMd
                        anchors.rightMargin: theme.spaceMd
                        anchors.topMargin: theme.spaceMd
                        spacing: theme.spaceSm
                        Text {
                            width: 44
                            text: modelData.time
                            color: theme.textMuted
                            font.family: theme.fontMono
                            font.pixelSize: theme.fontCaption
                        }
                        Text {
                            width: parent.width - 44 - theme.spaceSm
                            text: modelData.original
                            color: theme.textPrimary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSmall
                            elide: Text.ElideRight
                            visible: !item.expanded
                        }
                        Text {
                            width: parent.width - 44 - theme.spaceSm
                            text: "▾ 收起"
                            color: theme.textMuted
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                            visible: item.expanded
                        }
                    }

                    // 展开态：原始指令 + 增强结果两个区块
                    Column {
                        id: itemColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: headerRow.bottom
                        anchors.leftMargin: theme.spaceMd
                        anchors.rightMargin: theme.spaceMd
                        anchors.topMargin: theme.spaceSm
                        visible: item.expanded
                        spacing: theme.spaceSm

                        // 原始指令
                        Text {
                            width: parent.width
                            text: "原始指令"
                            color: theme.textMuted
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                            font.weight: Font.DemiBold
                        }
                        Text {
                            width: parent.width
                            text: modelData.original
                            color: theme.textPrimary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSmall
                            wrapMode: Text.Wrap
                        }

                        // 分隔
                        Rectangle {
                            width: parent.width
                            height: 1
                            color: theme.border
                        }

                        // 增强结果
                        Text {
                            width: parent.width
                            text: "增强结果"
                            color: theme.textMuted
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                            font.weight: Font.DemiBold
                        }
                        Text {
                            width: parent.width
                            text: modelData.enhanced
                            color: theme.textSecondary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSmall
                            wrapMode: Text.Wrap
                        }
                    }

                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: historyPanel.expandedIndex = item.expanded ? -1 : index
                    }
                }
            }
        }
    }
}
