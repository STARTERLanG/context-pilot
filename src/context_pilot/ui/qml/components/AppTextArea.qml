import QtQuick
import QtQuick.Controls

// 多行文本区。默认是可编辑的纯文本编辑框；markdown 为 true 时改为 Markdown
// 渲染显示（标题/加粗/斜体/列表/代码块/链接）。三种形态：
//   - markdown=false：现状纯文本编辑（TextEdit）。
//   - markdown=true 且 readOnly=true：只读 Markdown 渲染（增强结果）。
//   - markdown=true 且 readOnly=false：可编辑 + 「预览/源码」切换（原始指令）。
// copyable 为 true 时右上角显示复制按钮：点击发出 copyRequested(text)，
// 调用方执行复制后调用 flashCopied()，图标短暂切换为对勾作为轻量反馈。
Rectangle {
    id: root
    property alias text: edit.text
    property bool readOnly: false
    property bool markdown: false
    property bool previewMode: false  // 可编辑 Markdown 的预览态切换
    property bool copyable: false
    property bool copied: false  // 复制成功后的短暂反馈态
    signal copyRequested(string text)

    // 复制按钮 / 滚动条尺寸常量：留白计算复用，避免魔数散落在各处
    readonly property int scrollBarWidth: 6
    readonly property int copyBtnSize: 30
    // 右上角每个浮动按钮各自占的宽度（按钮 + 间隙）。滚动条单独算一次，
    // 避免两个按钮各加一遍导致留白虚高。
    readonly property int copyGutter: root.copyable
        ? root.copyBtnSize + theme.spaceSm
        : 0
    // 预览/源码切换按钮在右上时，同样要给文本区让出宽度，否则会压住背后的文字。
    readonly property int previewGutter: root.markdown && !root.readOnly
        ? root.copyBtnSize + theme.spaceSm
        : 0
    // 文本区右侧总共要让出的宽度：按钮组 + 滚动条 + 内边距（后者由 anchors 给）
    readonly property int rightGutter:
        root.copyGutter + root.previewGutter + root.scrollBarWidth
    // 空内容时禁用复制
    readonly property bool canCopy: root.copyable && root.text.length > 0

    // 是否处于 Markdown 渲染态（只读 Markdown 恒渲染；可编辑 Markdown 依预览态）
    readonly property bool renderingMarkdown:
        root.markdown && (root.readOnly || root.previewMode)
    // 光标是否在本控件内。单字母快捷键据它决定是否让行给打字
    readonly property bool editing: edit.activeFocus

    color: theme.surface
    border.width: 1
    border.color: edit.activeFocus ? theme.accent : theme.border
    radius: theme.radiusLg
    Behavior on border.color { ColorAnimation { duration: 100 } }

    function triggerCopy() {
        if (root.canCopy) {
            root.copyRequested(root.text)
        }
    }

    // 由调用方在复制成功后回调：图标短暂切换为对勾
    function flashCopied() {
        root.copied = true
        copyFeedback.restart()
    }

    // 预览/源码切换：仅在可编辑 Markdown 时可见
    function togglePreview() {
        root.previewMode = !root.previewMode
    }

    Timer {
        id: copyFeedback
        interval: 1200
        onTriggered: root.copied = false
    }
    onCopiedChanged: copyIcon.requestPaint()

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: theme.spaceMd
        // 右上浮着复制按钮或预览/源码按钮时，文本区右侧让出对应宽度，避免文字被压住
        anchors.rightMargin: theme.spaceMd + root.rightGutter
        contentWidth: width
        // 渲染态按 Markdown 文本高度滚动，编辑态按编辑区内容高度滚动
        contentHeight: root.renderingMarkdown ? md.implicitHeight : edit.contentHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        // 编辑态：纯文本输入（默认路径，行为与原先完全一致）
        TextEdit {
            id: edit
            width: flick.width
            visible: !root.renderingMarkdown
            color: theme.textPrimary
            font.family: theme.fontMono
            font.pixelSize: theme.fontBody
            readOnly: root.readOnly
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            selectionColor: theme.accent
            selectedTextColor: theme.textInverse
        }

        // 渲染态：Markdown 解析显示（标题/加粗/斜体/列表/代码块/链接）
        Text {
            id: md
            width: flick.width
            visible: root.renderingMarkdown
            text: root.text
            textFormat: Text.MarkdownText
            color: theme.textPrimary
            linkColor: theme.accent
            font.family: theme.fontFamily
            font.pixelSize: theme.fontBody
            wrapMode: Text.Wrap
        }

        ScrollBar.vertical: ScrollBar {
            id: vbar
            policy: ScrollBar.AsNeeded
            interactive: true                 // 移动端可触摸拖拽
            width: root.scrollBarWidth
            contentItem: Rectangle {
                // 宽度跟随 ScrollBar（6px），不写 implicitWidth 以避免
                // [undefined] to int 告警；仅保留视觉属性
                radius: 3
                color: vbar.pressed ? theme.accentHover
                     : vbar.hovered ? theme.accent
                     : theme.borderStrong
                opacity: vbar.pressed || vbar.hovered || vbar.active ? 1.0 : 0.6
                Behavior on color { ColorAnimation { duration: 100 } }
                Behavior on opacity { NumberAnimation { duration: 100 } }
            }
        }
    }

    // 右上角复制按钮：沿用项目 Canvas 图标规范（12×12 描边，与时钟/垃圾桶一致），
    // 颜色只取中性文字色——默认 textMuted 低对比，hover 加深到 textSecondary。
    // 右侧外移一个滚动条宽度，既不压滚动条也不压边框圆角。
    Rectangle {
        id: copyBtn
        visible: root.copyable
        enabled: root.canCopy
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: theme.spaceSm
        anchors.rightMargin: theme.spaceMd + root.scrollBarWidth
        width: root.copyBtnSize
        height: root.copyBtnSize
        radius: theme.radiusMd
        color: copyHover.hovered ? theme.surfaceHover : theme.surface
        border.width: 1
        border.color: copyBtn.activeFocus ? theme.borderStrong : theme.border
        opacity: root.canCopy ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: 90 } }
        Behavior on opacity { NumberAnimation { duration: 90 } }

        // 键盘可达：Tab 聚焦后回车 / 空格触发
        activeFocusOnTab: root.canCopy
        Keys.onReturnPressed: root.triggerCopy()
        Keys.onSpacePressed: root.triggerCopy()

        Accessible.role: Accessible.Button
        Accessible.name: root.copied ? "已复制" : "复制内容到剪贴板"
        Accessible.description: root.canCopy ? "复制当前文本框的全部内容"
                                             : "内容为空，暂不可复制"

        Canvas {
            id: copyIcon
            width: 12; height: 12
            anchors.centerIn: parent
            onPaint: {
                var c = getContext("2d")
                c.clearRect(0, 0, width, height)
                // 中性墨色：默认低对比，hover 略微加深
                c.strokeStyle = copyHover.hovered ? theme.textSecondary : theme.textMuted
                c.lineWidth = 1.2
                c.lineJoin = "round"
                c.lineCap = "round"

                if (root.copied) {
                    // 反馈态：对勾
                    c.beginPath()
                    c.moveTo(2, height * 0.55)
                    c.lineTo(width * 0.38, height * 0.82)
                    c.lineTo(width - 2, height * 0.22)
                    c.stroke()
                    return
                }
                // 复制图标：后页（右上露出）+ 前页（填底色遮住重叠部分）
                c.strokeRect(4.5, 1.5, 6, 6.5)
                c.fillStyle = copyBtn.color
                c.fillRect(1.5, 3.5, 7, 7)
                c.strokeRect(1.5, 3.5, 7, 7)
            }
        }

        HoverHandler {
            id: copyHover
            cursorShape: Qt.PointingHandCursor
            onHoveredChanged: copyIcon.requestPaint()
        }
        TapHandler { onTapped: root.triggerCopy() }
    }

    // 预览/源码切换胶囊：仅在「可编辑 Markdown」时出现，切换编辑与渲染两种形态。
    // 同时有复制按钮时向左让开一个按钮位，否则两个按钮会叠在同一处互相遮挡。
    Rectangle {
        id: previewBtn
        visible: root.markdown && !root.readOnly
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: theme.spaceSm
        anchors.rightMargin: theme.spaceMd + root.scrollBarWidth
                             + (root.copyable ? root.copyBtnSize + theme.spaceSm : 0)
        width: previewLabel.implicitWidth + theme.spaceMd
        height: root.copyBtnSize
        radius: theme.radiusMd
        color: previewHover.hovered ? theme.surfaceHover : theme.surface
        border.width: 1
        border.color: theme.border
        Text {
            id: previewLabel
            anchors.centerIn: parent
            text: root.previewMode ? "源码" : "预览"
            color: theme.textSecondary
            font.family: theme.fontFamily
            font.pixelSize: theme.fontCaption
        }
        HoverHandler { id: previewHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: root.togglePreview() }
        Accessible.role: Accessible.Button
        Accessible.name: root.previewMode ? "切换到源码编辑" : "切换到 Markdown 预览"
    }
}
