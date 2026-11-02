import QtQuick

// 数字输入：减号 / 数值 / 加号。用于预算与超时。
Rectangle {
    id: root
    property int value: 0
    property int from: 0
    property int to: 999999
    property int stepSize: 1
    signal valueModified(int value)

    implicitHeight: 36
    implicitWidth: 150
    color: theme.surface
    radius: theme.radiusMd
    border.width: 1
    border.color: theme.border

    HoverHandler { cursorShape: Qt.PointingHandCursor }

    // 同理不在内部写 value：外部通常写 `value: xxx` 绑定，命令式赋值会冲掉
    // 它。这里只把目标值抛给使用方，由使用方写回数据源再经绑定回来显示。
    function _apply(delta) {
        var next = Math.max(root.from, Math.min(root.to, root.value + delta))
        if (next !== root.value) {
            root.valueModified(next)
        }
    }

    Row {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 2

        Rectangle {
            width: 28; height: parent.height
            radius: theme.radiusSm
            color: decHover.hovered ? theme.surfaceHover : "transparent"
            Text {
                anchors.centerIn: parent
                text: "−"
                color: root.value <= root.from ? theme.textMuted : theme.textPrimary
                font.pixelSize: theme.fontSubtitle
            }
            HoverHandler { id: decHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: root._apply(-root.stepSize) }
        }

        Item {
            width: parent.width - 28 * 2 - parent.spacing * 2
            height: parent.height
            TextInput {
                id: input
                anchors.centerIn: parent
                width: parent.width
                horizontalAlignment: TextInput.AlignHCenter
                verticalAlignment: TextInput.AlignVCenter
                text: root.value
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
                validator: IntValidator { bottom: root.from; top: root.to }
                onEditingFinished: {
                    var parsed = parseInt(text)
                    if (!isNaN(parsed)) {
                        root.valueModified(parsed)
                    }
                    text = root.value  // 无效输入或超出区间时回填实际值
                }
            }
        }

        Rectangle {
            width: 28; height: parent.height
            radius: theme.radiusSm
            color: incHover.hovered ? theme.surfaceHover : "transparent"
            Text {
                anchors.centerIn: parent
                text: "+"
                color: root.value >= root.to ? theme.textMuted : theme.textPrimary
                font.pixelSize: theme.fontSubtitle
            }
            HoverHandler { id: incHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: root._apply(root.stepSize) }
        }
    }
}
