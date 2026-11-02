import QtQuick
import QtQuick.Layouts

// 自适应高度的设置卡片（AppCard 的自动高度变体）。
// AppCard 高度需外部指定；设置页内容随列表条目增减而变化，故改为由内部
// ColumnLayout 的 implicitHeight 反推卡片高度 + 上下 padding，省去手算。
Rectangle {
    id: root
    Layout.fillWidth: true
    Layout.preferredHeight: content.implicitHeight + theme.spaceLg * 2

    default property alias items: content.data

    color: theme.surface
    border.width: 1
    border.color: theme.border
    radius: theme.radiusLg

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: theme.spaceLg
        spacing: theme.spaceLg
    }
}
