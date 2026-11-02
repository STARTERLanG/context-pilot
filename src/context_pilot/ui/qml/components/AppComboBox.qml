import QtQuick
import QtQuick.Controls

// 下拉选择框（36×36 描边卡片 + 自绘箭头 + ListView 弹层）。
// 用于「获取模型」后的模型选择：比分段器更适合数量不定的长列表。
Rectangle {
    id: root
    property var model: []
    property string currentText: ""
    property string placeholder: "请先获取模型"
    signal activated(string text)

    implicitHeight: 36
    implicitWidth: 180
    radius: theme.radiusMd
    color: theme.surface
    border.width: 1
    border.color: popup.visible ? theme.accent : theme.border
    Behavior on border.color { ColorAnimation { duration: 100 } }

    Text {
        anchors.left: parent.left
        anchors.right: chevron.left
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: theme.spaceMd
        anchors.rightMargin: theme.spaceXs
        text: root.currentText.length > 0 ? root.currentText : root.placeholder
        color: root.currentText.length > 0 ? theme.textPrimary : theme.textMuted
        font.family: theme.fontFamily
        font.pixelSize: theme.fontBody
        elide: Text.ElideRight
    }

    // 箭头：捕获态旋转 180°（与展开方向一致）
    Canvas {
        id: chevron
        width: 10; height: 10
        anchors.right: parent.right
        anchors.rightMargin: theme.spaceMd
        anchors.verticalCenter: parent.verticalCenter
        rotation: popup.visible ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: 120 } }
        onRotationChanged: requestPaint()
        onPaint: {
            var c = getContext("2d")
            c.clearRect(0, 0, width, height)
            c.strokeStyle = popup.visible ? theme.accent : theme.textMuted
            c.lineWidth = 1.4
            c.lineCap = "round"
            c.lineJoin = "round"
            c.beginPath()
            c.moveTo(1.5, height * 0.38)
            c.lineTo(width / 2, height * 0.68)
            c.lineTo(width - 1.5, height * 0.38)
            c.stroke()
        }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: root.model.length > 0 ? popup.open() : undefined }

    Popup {
        id: popup
        x: 0
        y: root.height + 4
        width: root.width
        padding: 4
        height: Math.min(root.model.length * 30 + 8, 200)
        modal: true
        dim: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: theme.radiusMd
            color: theme.surface
            border.width: 1
            border.color: theme.border
        }

        contentItem: ListView {
            id: list
            clip: true
            model: root.model
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { width: 6; policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                required property string modelData
                required property int index
                width: list.width
                height: 30
                radius: theme.radiusSm
                color: itemHover.hovered ? theme.surfaceHover : "transparent"

                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: theme.spaceMd
                    anchors.rightMargin: theme.spaceMd
                    text: modelData
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    elide: Text.ElideRight
                }

                HoverHandler { id: itemHover; cursorShape: Qt.PointingHandCursor }
                TapHandler {
                    onTapped: {
                        root.currentText = modelData
                        popup.close()
                        root.activated(modelData)
                    }
                }
            }
        }
    }
}
