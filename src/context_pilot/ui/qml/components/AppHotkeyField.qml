import QtQuick

// 热键捕获框：点击 → 进入捕获态 → 下一次按键由 Python 侧转成 "ctrl+shift+e"
// 形式回填；Esc 取消并回滚到进入前的值。
// 只读 TextInput 只用于取得键盘焦点并拦截按键，可见文案由 Text 呈现。
Rectangle {
    id: root
    property string target: "hotkey"  // hotkey / toggle：决定写入配置里的哪个字段
    property string text: ""
    property string placeholder: "点击后按下组合键"
    property bool capturing: false
    property string backup: ""  // 进入捕获态前的旧值，Esc 回滚用

    implicitHeight: 36
    radius: theme.radiusMd
    color: root.capturing ? theme.accentSoft : theme.surface
    border.width: 1
    border.color: root.capturing ? theme.accent
                                 : (input.activeFocus ? theme.accent : theme.border)
    Behavior on border.color { ColorAnimation { duration: 100 } }
    Behavior on color { ColorAnimation { duration: 100 } }

    Text {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: theme.spaceMd
        anchors.rightMargin: theme.spaceMd
        text: root.capturing ? "请按下组合键…（Esc 取消）"
                             : (root.text.length > 0 ? root.text : root.placeholder)
        color: root.capturing ? theme.accent
                              : (root.text.length > 0 ? theme.textPrimary : theme.textMuted)
        font.family: theme.fontFamily
        font.pixelSize: theme.fontBody
        elide: Text.ElideRight
    }

    TextInput {
        id: input
        anchors.fill: parent
        readOnly: true
        opacity: 0          // 不可见：仅承接焦点与按键
        cursorVisible: false

        Keys.onPressed: (event) => {
            // 一律吞掉按键，避免空格/回车等被当成文本处理
            event.accepted = true
            if (event.key === Qt.Key_Escape) {
                root.text = root.backup
                root.capturing = false
                return
            }
            var sequence = settings.captureHotkeyFor(root.target, event.key, event.modifiers)
            if (sequence.length > 0) {
                root.text = sequence
                root.capturing = false
            }
        }

        // 失焦即退出捕获态（点到别处不会卡在「请按下组合键」）
        onActiveFocusChanged: {
            if (!activeFocus && root.capturing) {
                root.text = root.backup
                root.capturing = false
            }
        }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
    TapHandler {
        onTapped: {
            root.backup = root.text
            root.capturing = true
            input.forceActiveFocus()
        }
    }
}
