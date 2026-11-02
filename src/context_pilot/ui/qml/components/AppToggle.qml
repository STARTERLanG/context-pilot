import QtQuick

// 开关。比默认复选框更贴近现代界面。
Item {
    id: root
    property string text: ""
    property bool checked: false
    signal toggled(bool checked)

    implicitHeight: 24
    implicitWidth: row.implicitWidth

    Row {
        id: row
        anchors.verticalCenter: parent.verticalCenter
        spacing: theme.spaceMd

        Rectangle {
            id: track
            anchors.verticalCenter: parent.verticalCenter
            width: 40
            height: 22
            radius: theme.radiusFull
            color: root.checked ? theme.accent : theme.surfaceActive
            border.width: 1
            border.color: root.checked ? theme.accent : theme.borderStrong
            Behavior on color { ColorAnimation { duration: 120 } }

            Rectangle {
                id: knob
                width: 16
                height: 16
                radius: theme.radiusFull
                color: theme.surface
                y: 2
                x: root.checked ? track.width - width - 3 : 3
                Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
            }
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: theme.textPrimary
            font.family: theme.fontFamily
            font.pixelSize: theme.fontBody
        }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
    TapHandler {
        // 不在内部写 checked：外部通常以 `checked: xxx` 声明式绑定使用它，
        // 命令式赋值会把绑定冲掉、此后外部值变了也不再刷新。改为只抛意图
        // （目标值），由使用方写回数据源，再经绑定回流到 checked。
        onTapped: root.toggled(!root.checked)
    }
}
