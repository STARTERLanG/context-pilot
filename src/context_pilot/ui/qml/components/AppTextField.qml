import QtQuick

// 单行输入框。聚焦时描边变强调色。
Rectangle {
    id: root
    property alias text: input.text
    property string placeholderText: ""
    property int echoMode: TextInput.Normal
    property bool readOnly: false
    signal editingFinished()

    implicitHeight: 36
    radius: theme.radiusMd
    color: theme.surface
    border.width: 1
    border.color: input.activeFocus ? theme.accent : theme.border
    Behavior on border.color { ColorAnimation { duration: 100 } }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: theme.spaceMd
        anchors.right: parent.right
        anchors.rightMargin: theme.spaceMd
        anchors.verticalCenter: parent.verticalCenter
        text: root.placeholderText
        visible: input.text.length === 0
        color: theme.textMuted
        font.family: theme.fontFamily
        font.pixelSize: theme.fontBody
        elide: Text.ElideRight
    }

    TextInput {
        id: input
        anchors.fill: parent
        anchors.leftMargin: theme.spaceMd
        anchors.rightMargin: theme.spaceMd
        verticalAlignment: TextInput.AlignVCenter
        color: root.readOnly ? theme.textSecondary : theme.textPrimary
        font.family: theme.fontFamily
        font.pixelSize: theme.fontBody
        selectionColor: theme.accent
        selectedTextColor: theme.textInverse
        readOnly: root.readOnly
        echoMode: root.echoMode
        clip: true
        onEditingFinished: root.editingFinished()
    }
}
