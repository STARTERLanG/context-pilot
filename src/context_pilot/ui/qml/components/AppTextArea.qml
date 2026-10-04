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

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    }
}
