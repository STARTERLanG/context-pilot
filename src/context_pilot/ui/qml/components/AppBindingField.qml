import QtQuick
import QtQuick.Layouts

// 单个动作的绑定捕获框。与 AppHotkeyField（全局热键）分工：
//  - 本组件面向「窗口内动作」，按键经 shortcut_ctl 落到指定动作；
//  - 取消语义不同：允许绑单键的动作（close）按下 Esc 是**绑定 Esc**而不是取消，
//    此时取消改用 Delete / Backspace——否则用户永远无法把 Esc 绑回去。
//  （AppHotkeyField 的 Esc 仍是取消：全局热键按规矩必须有修饰键。）
Rectangle {
    id: root

    property string actionId: ""
    property string display: ""
    property bool allowNaked: false
    property bool modified: false
    property string level: ""          // "" | "error" | "warning"
    property string message: ""
    property bool capturing: false
    property string notice: ""         // 捕获被拒时的短提示，2 秒后自动消失

    implicitWidth: 150
    implicitHeight: 34
    radius: theme.radiusMd
    color: root.capturing ? theme.accentSoft : theme.surface
    border.width: 1
    border.color: root.level === "error" ? theme.danger
                : root.level === "warning" ? theme.warning
                : root.capturing ? theme.accent
                : root.message.length > 0 ? theme.warning
                : (input.activeFocus ? theme.accent : theme.border)
    Behavior on border.color { ColorAnimation { duration: 100 } }

    Timer {
        interval: 2400
        running: root.notice.length > 0
        repeat: false
        onTriggered: root.notice = ""
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spaceMd
        anchors.rightMargin: theme.spaceSm
        spacing: theme.spaceXs

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            text: root.capturing
                  ? (root.notice.length > 0 ? root.notice : root.hintText())
                  : (root.display.length > 0 ? root.display : "未绑定")
            color: root.capturing ? theme.accent
                 : root.level === "error" ? theme.danger
                 : root.display.length > 0 ? theme.textPrimary : theme.textMuted
            font.family: theme.fontFamily
            font.pixelSize: theme.fontBody
            elide: Text.ElideRight
        }

        // 改动过才出现：一键回到当前方案的默认值
        Rectangle {
            Layout.preferredWidth: 42
            Layout.preferredHeight: 22
            Layout.alignment: Qt.AlignVCenter
            visible: root.modified && !root.capturing
            radius: theme.radiusFull
            color: resetHover.hovered ? theme.surfaceActive : theme.surfaceHover
            border.width: 1
            border.color: theme.border

            Text {
                anchors.centerIn: parent
                text: "重置"
                color: theme.textSecondary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
            }
            HoverHandler { id: resetHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: shortcut_ctl.resetAction(root.actionId) }
            Accessible.role: Accessible.Button
            Accessible.name: "重置为方案默认值"
        }
    }

    function hintText() {
        return root.allowNaked ? "按组合键，或按 Esc" : "需按 Ctrl / Alt + 键"
    }

    function rejectNotice() {
        return root.allowNaked ? "无效：请按组合键或 Esc" : "无效：必须带 Ctrl / Alt"
    }

    TextInput {
        id: input
        anchors.fill: parent
        readOnly: true
        opacity: 0
        cursorVisible: false

        Keys.onPressed: (event) => {
            // 一律吞掉，免得空格/回车被当成文本处理
            event.accepted = true

            var bare = (event.modifiers === Qt.NoModifier)
            // Delete / Backspace 恒为取消，给「允许单键」的动作留一条退出路径
            if (bare && (event.key === Qt.Key_Backspace || event.key === Qt.Key_Delete)) {
                root.capturing = false
                root.notice = ""
                return
            }
            // 不允许单键时，Esc 才是取消；允许单键时 Esc 是要绑定的那个键
            if (bare && event.key === Qt.Key_Escape && !root.allowNaked) {
                root.capturing = false
                root.notice = ""
                return
            }
            // 交给控制器判定：组合键、编辑保留键、单键白名单都在 core.shortcuts 里。
            // 返回空串表示这次按键不成绑定——保持捕获态并给出原因，不让用户猜。
            var seq = shortcut_ctl.capture(root.actionId, event.key, event.modifiers)
            if (seq === "") {
                // 控制器给的是具体原因（「与 增强 重复」之类），比笼统的
                // 「无效」有用得多；拿不到原因时再退回通用提示。
                root.notice = shortcut_ctl.rejectReason || root.rejectNotice()
                return
            }
            root.notice = ""
            root.capturing = false
        }

        // 点到别处也要退出捕获态，否则会一直卡在「请按组合键」
        onActiveFocusChanged: {
            if (!activeFocus && root.capturing) {
                root.capturing = false
                root.notice = ""
            }
        }
    }

    HoverHandler { cursorShape: root.capturing ? Qt.ArrowCursor : Qt.PointingHandCursor }
    TapHandler {
        onTapped: {
            if (root.capturing) return
            root.notice = ""
            root.capturing = true
            input.forceActiveFocus()
        }
    }
}
