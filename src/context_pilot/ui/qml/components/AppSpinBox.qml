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

    function _apply(delta) {
        var next = Math.max(root.from, Math.min(root.to, root.value + delta))
        if (next !== root.value) {
            root.value = next
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
                        root.value = parsed
                        root.valueModified(parsed)
                    } else {
                        text = root.value
                    }
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
