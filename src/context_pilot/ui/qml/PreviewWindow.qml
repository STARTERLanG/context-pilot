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

    // 页面状态：settingsLoaded 首次进入后即保持为真（设置页实例常驻，保留
    // 分类、展开项与未保存输入）；settingsOpen 决定当前展示哪一页。
    property bool settingsOpen: false
    property bool settingsLoaded: false

    // ---------- 窗口内快捷键（PRD 三十一章；键位由设置页「窗口快捷键」决定）----------
    // 这里不再写死任何键位：每条 Shortcut 的序列都绑到 shortcut_ctl，用户在设置
    // 页改完即时生效，不必重启。
    //
    // 也正因如此，「判断焦点给打字让路」那套补丁可以彻底删掉：规则要求除 Esc
    // 外一律组合键，单字母键（从前的 E/D/C/R）不会再和输入冲突。靠 enabled 门控
    // 单键是治标——换个没被门控的键就复发，从规则上禁止才是治本。
    readonly property bool onMainPage: !root.settingsOpen

    Shortcut {
        // Esc 恒为「退一层」：设置页先回主页面（浮窗惯例），主页面才关窗。
        // 「关闭窗口」若恰好也绑在 Esc 上，则由下面专门那条接管——两者互斥，
        // 否则一次 Esc 会关两次窗。
        sequence: "Esc"
        enabled: root.settingsOpen || !shortcut_ctl.escIsClose
        onActivated: root.settingsOpen ? root.backToMain() : windowCtl.close()
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.close || []
        enabled: root.onMainPage
        onActivated: windowCtl.close()
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.enhance || []
        enabled: root.onMainPage
        onActivated: root.triggerEnhance()
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.rerun || []
        enabled: root.onMainPage
        onActivated: root.triggerRerun()
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.use || []
        enabled: root.onMainPage
        onActivated: root.triggerUse()
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.view_enhanced || []
        enabled: root.onMainPage
        onActivated: root.currentView = 0
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.view_diff || []
        enabled: root.onMainPage
        onActivated: root.currentView = 1
    }
    Shortcut {
        sequences: shortcut_ctl.sequences.view_context || []
        enabled: root.onMainPage
        onActivated: root.currentView = 2
    }

    // 从输入框/结果框之外触发增强：优先用输入框内容。
    // 与按钮同一门槛：未选定增强目标模型时不发起增强（热键也不能绕过）。
    function triggerEnhance() {
        if (!root.onMainPage || preview.enhancing || !sessionCtl.hasModelSelected) return
        preview.enhance(promptArea.text)
    }

    // 重新增强：用上一次提交的原文重跑（忽略输入框里的后续编辑）
    function triggerRerun() {
        if (!root.onMainPage || preview.enhancing || !sessionCtl.hasModelSelected) return
        preview.rerun()
    }

    function triggerUse() {
        if (!root.onMainPage) return
        if (preview.status !== "完成" || enhancedArea.text.length === 0) return
        preview.use(enhancedArea.text)
    }

    // 进入设置页：几何完全不变，只切换内容区的内容
    function openSettings() {
        root.settingsLoaded = true
        root.settingsOpen = true
    }

    // 返回主页面：主页面 Item 全程未被销毁，历史/输入/滚动位置原样恢复
    function backToMain() {
        root.settingsOpen = false
    }

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

            // 右侧：设置入口 + 窗口控制按钮（最小化 / 最大化 / 关闭）
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: theme.spaceXs

                // 设置入口：齿轮图标，与窗口控制按钮同尺寸（34×30）同 hover 底色；
                // 进入设置页后自身隐藏（已在设置页，避免自指入口）。
                Rectangle {
                    id: settingsBtn
                    objectName: "settingsBtn"
                    visible: !root.settingsOpen
                    width: 34; height: 30
                    radius: theme.radiusSm
                    color: settingsHover.hovered ? theme.surfaceHover : "transparent"
                    anchors.verticalCenter: parent.verticalCenter
                    Canvas {
                        width: 14; height: 14
                        anchors.centerIn: parent
                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)
                            c.strokeStyle = theme.textSecondary
                            c.lineWidth = 1.3
                            c.lineCap = "round"
                            // 齿圈
                            c.beginPath()
                            c.arc(width / 2, height / 2, 4.6, 0, Math.PI * 2)
                            c.stroke()
                            // 六个齿：以中心为准向外放射短线
                            for (var i = 0; i < 6; i++) {
                                var a = i * Math.PI / 3
                                var cx = width / 2 + Math.cos(a) * 5.6
                                var cy = height / 2 + Math.sin(a) * 5.6
                                c.beginPath()
                                c.moveTo(cx - Math.cos(a) * 1.6, cy - Math.sin(a) * 1.6)
                                c.lineTo(cx + Math.cos(a) * 1.6, cy + Math.sin(a) * 1.6)
                                c.stroke()
                            }
                            // 内圈
                            c.beginPath()
                            c.arc(width / 2, height / 2, 1.6, 0, Math.PI * 2)
                            c.stroke()
                        }
                    }
                    HoverHandler { id: settingsHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: root.openSettings() }

                    Accessible.role: Accessible.Button
                    Accessible.name: "打开设置"
                }

                // 与窗口控制按钮之间留一段余量，避免误点
                Rectangle {
                    visible: !root.settingsOpen
                    width: 1; height: 16
                    color: theme.border
                    anchors.verticalCenter: parent.verticalCenter
                }

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

        // ---------- 主体（主页面内容） ----------
        // 与设置页共用同一矩形（顶栏下 + 卡片内的同一套边距）；隐藏而非销毁，
        // 返回时便能保持输入框内容、历史弹窗状态与滚动位置。
        ColumnLayout {
            id: mainContent
            objectName: "mainContent"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: topBar.bottom
            anchors.bottom: bottomBar.top
            anchors.leftMargin: theme.spaceXl
            anchors.rightMargin: theme.spaceXl
            anchors.topMargin: theme.spaceLg
            anchors.bottomMargin: theme.spaceLg
            spacing: theme.spaceMd
            visible: !root.settingsOpen

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

                // 输出风格：决定本次增强的详细程度、格式自由度与长度上限。
                // 放在输入区标题行右侧，语义上是「这次希望怎么输出」，与
                // 「项目/模型」这类会话级选择区分开，也避免挤占中间行宽度。
                // 不设 label（收起态只显示风格名），并加宽让「简洁润色」等
                // 文案完整显示，不再被 elide 截断。
                AppSelect {
                    id: styleSelect
                    objectName: "styleSelect"
                    Layout.preferredWidth: 150
                    Layout.minimumWidth: 120
                    Layout.maximumWidth: 180
                    label: ""
                    options: sessionCtl.styles
                    currentId: sessionCtl.currentStyle
                    currentText: sessionCtl.currentStyleLabel
                    emptyText: "结构化增强"
                    Accessible.description: "选择输出风格与长度上限"
                    onSelected: (id) => sessionCtl.selectStyle(id)
                }

                Item { Layout.fillWidth: true }

                // 清空（图标 + 文字胶囊，同时清空原始指令与增强结果两个输入框）
                Rectangle {
                    id: clearBtn
                    objectName: "clearBtn"
                    Layout.alignment: Qt.AlignVCenter
                    width: clearContent.width + theme.spaceMd
                    height: 24
                    radius: theme.radiusFull
                    color: clearHover.hovered ? theme.surfaceActive : "transparent"
                    border.width: 1
                    border.color: clearHover.hovered ? theme.borderStrong : theme.border
                    Behavior on color { ColorAnimation { duration: 90 } }
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
                    markdown: true
                    // 可编辑：单向初始化，避免与只读 Property 双向绑定导致输入被覆盖
                    text: ""
                    Component.onCompleted: promptArea.text = preview.originalPrompt
                }
                // 仅新会话开始时同步输入框（begin 用剪贴板覆盖 originalPrompt）。
                // 不监听 changed：set_result/set_failed 也会 emit changed，
                // 若同步会覆盖用户编辑或把残留内容写回输入框。
                Connections {
                    target: preview
                    function onSessionStarted() {
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

            // 视图切换 + 项目/模型选择 + 增强按钮（增强在行尾，选择框紧贴分段器）
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceSm

                // 分段器与增强按钮的最小宽度等于自身宽度：空间不足时优先保证这
                // 两个不被压扁，让中间的两个下拉让步（内部文字做了 elide）。
                AppSegmented {
                    Layout.fillWidth: false
                    Layout.minimumWidth: implicitWidth
                    // 三个视图标签收紧段间距与最小段宽，为行尾的「增强」主按钮腾空间
                    segmentMinWidth: 72
                    segmentSpacing: 2
                    options: root.views
                    currentIndex: root.currentView
                    onActivated: (index) => root.currentView = index
                }

                AppSelect {
                    objectName: "projectSelect"
                    Layout.preferredWidth: 128
                    Layout.minimumWidth: 96
                    Layout.maximumWidth: 200
                    label: "项目"
                    options: sessionCtl.projects
                    currentId: sessionCtl.currentProjectId
                    currentText: sessionCtl.currentProjectLabel
                    emptyText: "暂无项目"
                    Accessible.description: "选择本次增强使用的项目"
                    onSelected: (id) => sessionCtl.selectProject(id)
                }

                // 增强目标：候选只含「已生效」的模型配置（未生效的不出现）。
                // 多条生效时必须由用户明确选一条——未选时下拉以告警色描边、
                // 显示提示文案，增强按钮同步置灰（见 enhanceBtn.enabled）。
                AppSelect {
                    objectName: "modelSelect"
                    Layout.preferredWidth: 156
                    Layout.minimumWidth: 96
                    Layout.maximumWidth: 220
                    label: "模型"
                    options: sessionCtl.models
                    currentId: sessionCtl.currentModelId
                    currentText: sessionCtl.currentModelLabel
                    emptyText: sessionCtl.modelsHint
                    attention: !sessionCtl.hasModelSelected
                    Accessible.description: "选择本次增强使用的模型"
                    onSelected: (id) => sessionCtl.selectModel(id)
                }

                Item { Layout.fillWidth: true }

                // 增强按钮：手动触发增强流程（取消自动增强后唯一的增强入口）。
                // 放大到与同行控件等高（38），作为主要互动入口更醒目。
                // 两种禁用原因：增强进行中（防重复点击）、尚未选定增强目标模型。
                Rectangle {
                    id: enhanceBtn
                    objectName: "enhanceBtn"
                    Layout.alignment: Qt.AlignVCenter
                    Layout.minimumWidth: enhanceLabel.implicitWidth + theme.spaceLg * 2
                    width: enhanceLabel.implicitWidth + theme.spaceLg * 2
                    height: 38
                    radius: theme.radiusMd
                    readonly property bool canEnhance: !preview.enhancing && sessionCtl.hasModelSelected
                    enabled: canEnhance
                    opacity: canEnhance ? 1 : 0.5
                    color: enhanceHover.hovered && canEnhance ? theme.accentHover : theme.accent
                    Behavior on color { ColorAnimation { duration: 90 } }
                    Behavior on opacity { NumberAnimation { duration: 90 } }
                    Text {
                        id: enhanceLabel
                        anchors.centerIn: parent
                        text: "✨ 增强提示词"
                        color: theme.textInverse
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontBody
                        font.weight: Font.DemiBold
                    }
                    HoverHandler {
                        id: enhanceHover
                        cursorShape: enhanceBtn.canEnhance ? Qt.PointingHandCursor : Qt.ArrowCursor
                    }
                    TapHandler {
                        enabled: enhanceBtn.canEnhance
                        onTapped: preview.enhance(promptArea.text)
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: "增强提示词"
                }
            }

            // ---------- 三视图容器（增强结果 / 差异 / 上下文）----------
            // 三个视图互斥显示。必须放进同一个 fillHeight 容器：若各自作为
            // ColumnLayout 的 fillHeight 子项并用 visible 切换，切换后布局不会
            // 重新分配空间，导致后两个视图宽高塌缩为 0（内容不可见）。
            Item {
                id: viewContainer
                Layout.fillWidth: true
                Layout.fillHeight: true

                // ---------- 增强结果 ----------
                // 可编辑（PRD 第三十八章 MVP 的「✓ Edit」）：默认展示 Markdown 渲染
                // 效果，点右上「源码」即可直接改。text 用单向初始化而非属性绑定——
                // 双向绑定会在用户敲键时把内容写回模型、并被下一次 changed 覆盖。
                AppTextArea {
                    id: enhancedArea
                    anchors.fill: parent
                    visible: root.currentView === 0
                    readOnly: false
                    markdown: true
                    previewMode: true
                    copyable: true
                    text: ""
                    Component.onCompleted: enhancedArea.text = preview.enhancedPrompt
                    // 只在增强成功时回填；失败/状态刷新不动用户已编辑的内容
                    Connections {
                        target: preview
                        function onResultReady() {
                            enhancedArea.text = preview.enhancedPrompt
                        }
                    }
                    // 复制由模型写入剪贴板，成功后组件内图标短暂切换为对勾作为反馈
                    onCopyRequested: (text) => {
                        if (preview.copyText(text)) {
                            enhancedArea.flashCopied()
                        }
                    }
                }

                // ---------- 差异视图 ----------
                ListView {
                    anchors.fill: parent
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
                    anchors.fill: parent
                    visible: root.currentView === 2
                    clip: true
                    model: preview.contextRows
                    spacing: theme.spaceSm
                    delegate: Rectangle {
                        id: ctxCard
                        required property var modelData
                        // 点击展开/收起命中片段
                        property bool expanded: false
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
                            // 点击展开的命中片段：精确展示被选中的代码/文本
                            ColumnLayout {
                                visible: ctxCard.expanded
                                spacing: theme.spaceXs
                                // 片段行号标签
                                Text {
                                    visible: modelData.lineStart > 0
                                    text: "命中行 " + modelData.lineStart + (modelData.lineEnd > modelData.lineStart ? "–" + modelData.lineEnd : "")
                                    color: theme.textMuted
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.fontCaption
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: snippetText.implicitHeight + theme.spaceMd * 2
                                    radius: theme.radiusSm
                                    color: theme.background
                                    border.width: 1
                                    border.color: theme.border
                                    Text {
                                        id: snippetText
                                        anchors.fill: parent
                                        anchors.margins: theme.spaceMd
                                        text: modelData.snippet
                                        color: theme.textSecondary
                                        font.family: theme.fontMono
                                        font.pixelSize: theme.fontSmall
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }
                        }

                        // 点击整张卡片切换展开态
                        TapHandler {
                            cursorShape: Qt.PointingHandCursor
                            onTapped: ctxCard.expanded = !ctxCard.expanded
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.source + (ctxCard.expanded ? "（已展开）" : "")
                    }
                }
            }
        }

        // ---------- 底部：Token 统计 + 操作（主页面专属，随主页面一起隐藏） ----------
        Item {
            id: bottomBar
            objectName: "bottomBar"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: theme.spaceXl
            anchors.rightMargin: theme.spaceXl
            anchors.bottomMargin: theme.spaceLg
            height: 44
            visible: !root.settingsOpen

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
                        + (preview.tokenStats.budget > 0
                           ? " / " + preview.tokenStats.budget : "")
                    color: preview.overBudget ? theme.danger : theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                }
                // 超出上下文预算时的告警标签：预算对 saving token 的价值在于
                // 能被看见——只显示绝对值等于没有上限，用户不知道自己超没超。
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: preview.overBudget
                    width: overBudgetText.implicitWidth + theme.spaceMd
                    height: 18
                    radius: 9
                    color: theme.dangerSoft
                    border.width: 1
                    border.color: theme.danger
                    Text {
                        id: overBudgetText
                        anchors.centerIn: parent
                        text: "超预算 " + Math.round(
                            (preview.tokenStats.total / preview.tokenStats.budget - 1) * 100) + "%"
                        color: theme.danger
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontCaption
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: theme.spaceSm

                // 使用增强结果：把增强文本交给目标 Agent（写剪贴板，PRD 第十章
                // Use Enhanced）。仅在增强完成且有内容时可用，避免空/未完成时误触发。
                // 传 enhancedArea.text（结果框当前内容）而非模型值：用户手动编辑过
                // 的内容必须被带走，否则「Edit」形同虚设。
                AppButton {
                    text: "使用增强结果"
                    variant: "primary"
                    enabled: preview.status === "完成" && enhancedArea.text.length > 0
                    implicitWidth: 112
                    implicitHeight: 32
                    onClicked: preview.use(enhancedArea.text)
                }
            }
        }

        // ---------- 设置页 ----------
        // 与主页面内容区完全同址同尺寸（顶栏下、卡片内同一套边距），切换时只换
        // 这块矩形里的渲染内容：窗口尺寸、圆角与阴影都不变，不会有布局跳动。
        // Loader 首次进入后才实例化并常驻：设置页内部的分类、展开项、未提交输入
        // 在来回切换之间得以保留。
        Loader {
            id: settingsLoader
            objectName: "settingsLoader"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: topBar.bottom
            anchors.bottom: parent.bottom
            anchors.leftMargin: theme.spaceXl
            anchors.rightMargin: theme.spaceXl
            anchors.topMargin: theme.spaceLg
            anchors.bottomMargin: theme.spaceLg
            active: root.settingsLoaded
            source: "settings/SettingsPage.qml"
            visible: root.settingsOpen
        }

        Connections {
            target: settingsLoader.item
            function onBackRequested() {
                root.backToMain()
            }
        }
    }

    // ---------- 历史记录弹窗 ----------
    Popup {
        id: historyPopup
        objectName: "historyPopup"
        // 相对根节点居中：card 四周还有 shadowMargin 的阴影留白，按 card 算会整体偏左上
        x: (root.width - width) / 2
        y: (root.height - height) / 2
        width: Math.min(root.width - 80, 520)
        height: Math.min(root.height - 80, 440)
        padding: theme.spaceLg
        modal: true
        // 不拿焦点的话 Esc 会被窗口级快捷键吃掉，弹窗自己收不到 CloseOnEscape
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        // 关闭时收起展开项：留着的展开状态下次打开会落在另一条记录上
        onClosed: historyPanel.expandedKey = -1

        background: Rectangle {
            radius: theme.radiusLg
            color: theme.surface
            border.width: 1
            border.color: theme.border
        }

        contentItem: ColumnLayout {
            id: historyPanel
            spacing: theme.spaceMd

            // 当前展开的历史条目 key（-1 表示全部收起）。
            // 用 key 而不是下标：新记录插在最前会让下标整体后移，展开的就成了别人。
            property int expandedKey: -1

            // 标题行用 RowLayout：Row 里的 Layout.fillWidth 不生效，
            // 关闭按钮会紧贴标题而不是靠右。
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spaceSm
                Text {
                    Layout.fillWidth: true
                    text: "历史优化记录"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    Layout.preferredWidth: 26
                    Layout.preferredHeight: 26
                    radius: theme.radiusSm
                    color: closePopHover.hovered ? theme.surfaceHover : "transparent"
                    // 叉号用 Canvas 画：字体符号在缺字时会渲染成方块
                    Canvas {
                        width: 10; height: 10
                        anchors.centerIn: parent
                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)
                            c.strokeStyle = closePopHover.hovered ? theme.textPrimary
                                                                    : theme.textSecondary
                            c.lineWidth = 1.4
                            c.lineCap = "round"
                            c.beginPath()
                            c.moveTo(1, 1); c.lineTo(width - 1, height - 1)
                            c.moveTo(width - 1, 1); c.lineTo(1, height - 1)
                            c.stroke()
                        }
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
                boundsBehavior: Flickable.StopAtBounds
                // 与其他列表统一：6px 细滚动条，按需出现
                ScrollBar.vertical: ScrollBar {
                    id: historyBar
                    width: 6
                    policy: ScrollBar.AsNeeded
                }

                delegate: Rectangle {
                    id: item
                    required property var modelData
                    // 只按 key 判断展开：下标会随新记录插入而整体后移
                    readonly property bool expanded: historyPanel.expandedKey === modelData.key

                    // 滚动条出现时让出它的宽度：否则条目压到滚动条下面，右侧文字被盖住
                    width: ListView.view.width - (historyBar.visible ? 8 : 0)
                    // 高度由内容撑开，不手算 margin：手算时 itemColumn 的 topMargin
                    // 没被计入，展开后正文会溢出圆角边框。
                    height: contentColumn.implicitHeight + theme.spaceMd * 2
                    radius: theme.radiusMd
                    // 卡片底色用 surface（白），与弹窗底色区分靠描边；
                    // 原先用 background(#F9FAFB) 与白色几乎无差，边界看不出来
                    color: item.expanded ? theme.surfaceActive
                         : itemHover.hovered ? theme.surfaceHover
                         : theme.surface
                    border.width: 1
                    border.color: item.expanded ? theme.borderStrong : theme.border
                    Behavior on height { NumberAnimation { duration: 120 } }

                    // 收起态点整张卡片展开；展开态只有「收起」负责收起——
                    // 正文要留给鼠标拖选，点正文不该把卡片收掉。
                    HoverHandler {
                        id: itemHover
                        enabled: !item.expanded
                        cursorShape: Qt.PointingHandCursor
                    }
                    TapHandler {
                        enabled: !item.expanded
                        onTapped: historyPanel.expandedKey = modelData.key
                    }

                    Column {
                        id: contentColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.leftMargin: theme.spaceMd
                        anchors.rightMargin: theme.spaceMd
                        anchors.topMargin: theme.spaceMd
                        spacing: item.expanded ? theme.spaceSm : 0

                        // 收起态：时间 + 原始指令摘要（单行）；展开态：时间 + 「收起」
                        Row {
                            id: headerRow
                            width: parent.width
                            spacing: theme.spaceSm
                            Text {
                                id: timeText
                                // 固定宽度会被 HH:MM:SS 撑爆（等宽字体下约 52px），
                                // 让文本自己决定宽度，右侧内容用剩余空间
                                text: modelData.time
                                color: theme.textMuted
                                font.family: theme.fontMono
                                font.pixelSize: theme.fontCaption
                            }
                            Text {
                                width: parent.width - timeText.width - theme.spaceSm
                                text: modelData.original
                                color: theme.textPrimary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontSmall
                                elide: Text.ElideRight
                                visible: !item.expanded
                            }
                            // 「收起」提示：文本 + Canvas 三角（不依赖字体符号）。
                            // 展开态下这里是唯一的收起入口，故自己带 hover 光标。
                            Row {
                                id: collapseHint
                                spacing: theme.spaceXs
                                visible: item.expanded
                                Text {
                                    text: "收起"
                                    color: collapseHover.hovered ? theme.textPrimary
                                                                 : theme.textMuted
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.fontCaption
                                }
                                HoverHandler {
                                    id: collapseHover
                                    cursorShape: Qt.PointingHandCursor
                                }
                                TapHandler {
                                    onTapped: historyPanel.expandedKey = -1
                                }
                                Canvas {
                                    width: 8; height: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    onPaint: {
                                        var c = getContext("2d")
                                        c.clearRect(0, 0, width, height)
                                        c.strokeStyle = theme.textMuted
                                        c.lineWidth = 1.2
                                        c.lineCap = "round"
                                        c.lineJoin = "round"
                                        c.beginPath()
                                        c.moveTo(1, height * 0.62)
                                        c.lineTo(width / 2, height * 0.32)
                                        c.lineTo(width - 1, height * 0.62)
                                        c.stroke()
                                    }
                                }
                            }
                        }

                        // 展开态：原始指令 + 增强结果两个区块
                        Column {
                            width: parent.width
                            visible: item.expanded
                            spacing: theme.spaceSm

                            Text {
                                width: parent.width
                                text: "原始指令"
                                color: theme.textMuted
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontCaption
                                font.weight: Font.DemiBold
                            }
                            // 正文可选中 / 可复制（Ctrl+C 走系统剪贴板）
                            SelectableText {
                                width: parent.width
                                text: modelData.original
                            }

                            Rectangle {
                                width: parent.width
                                height: 1
                                color: theme.border
                            }

                            Text {
                                width: parent.width
                                text: "增强结果"
                                color: theme.textMuted
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontCaption
                                font.weight: Font.DemiBold
                            }
                            SelectableText {
                                width: parent.width
                                text: modelData.enhanced
                                color: theme.textSecondary
                            }
                        }
                    }
                }
            }
        }
    }
}
