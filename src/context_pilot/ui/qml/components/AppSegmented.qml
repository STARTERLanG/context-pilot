import QtQuick

// 分段选择器。用于选项少的场景（如 stub / openai），比下拉框更直观。
Rectangle {
    id: root
    property var options: []
    property int currentIndex: 0
    signal activated(int index)

    implicitHeight: 38
    color: theme.surface
    radius: theme.radiusMd
    border.width: 1
    border.color: theme.border

    Row {
        id: row
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4

        Repeater {
            model: root.options
            delegate: Rectangle {
                required property int index
                required property string modelData

                width: (row.width - row.spacing * (root.options.length - 1)) / root.options.length
                height: row.height
                radius: theme.radiusSm
                color: index === root.currentIndex
                       ? theme.accent
                       : (segHover.hovered ? theme.surfaceHover : "transparent")
                Behavior on color { ColorAnimation { duration: 90 } }

                Text {
                    anchors.centerIn: parent
                    text: modelData
                    color: index === root.currentIndex ? theme.textInverse : theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontBody
                    font.weight: index === root.currentIndex ? Font.DemiBold : Font.Normal
                }

                HoverHandler { id: segHover; cursorShape: Qt.PointingHandCursor }
                TapHandler {
                    onTapped: {
                        root.currentIndex = index
                        root.activated(index)
                    }
                }
            }
        }
    }
}
