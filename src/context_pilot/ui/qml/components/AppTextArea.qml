import QtQuick
import QtQuick.Controls

// 多行可编辑文本区。增强结果是 Markdown 提示词，用等宽字体呈现。
Rectangle {
    id: root
    property alias text: edit.text
    property bool readOnly: false

    color: theme.surface
    border.width: 1
    border.color: edit.activeFocus ? theme.accent : theme.border
    radius: theme.radiusLg
    Behavior on border.color { ColorAnimation { duration: 100 } }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: theme.spaceMd
        contentWidth: width
        contentHeight: edit.contentHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        TextEdit {
            id: edit
            width: flick.width
            color: theme.textPrimary
            font.family: theme.fontMono
            font.pixelSize: theme.fontBody
            readOnly: root.readOnly
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            selectionColor: theme.accent
            selectedTextColor: theme.textInverse
        }

        ScrollBar.vertical: ScrollBar {
            id: vbar
            policy: ScrollBar.AsNeeded
            interactive: true                 // 移动端可触摸拖拽
            width: 6
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
}
