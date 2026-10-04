import QtQuick

// 带描边的面板容器。子元素通过默认属性直接放入，已内建 padding。
Rectangle {
    id: root
    default property alias items: inner.data
    property int padding: theme.spaceLg

    color: theme.surface
    border.width: 1
    border.color: theme.border
    radius: theme.radiusLg

    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
