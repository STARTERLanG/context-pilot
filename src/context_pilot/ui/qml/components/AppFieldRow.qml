import QtQuick
import QtQuick.Layouts

// 设置表单行：左侧标题 + 说明（可换行），右侧固定宽控件。
// 与主页面「历史记录 / 清空」胶囊同处一套间距与字号的视觉体系；右列默认 220px，
// 需要更宽的控件可由调用方覆盖 controlWidth。
RowLayout {
    id: root
    property string title: ""
    property string desc: ""
    property int controlWidth: 220
    default property alias control: controlBox.data

    spacing: theme.spaceLg

    Column {
        Layout.preferredWidth: 300
        Layout.alignment: Qt.AlignTop
        spacing: 2

        Text {
            width: parent.width
            text: root.title
            color: theme.textPrimary
            font.family: theme.fontFamily
            font.pixelSize: theme.fontBody
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
        }
        Text {
            width: parent.width
            visible: text.length > 0
            text: root.desc
            color: theme.textSecondary
            font.family: theme.fontFamily
            font.pixelSize: theme.fontSmall
            wrapMode: Text.Wrap
        }
    }

    Item { Layout.fillWidth: true }

    // 控件槽位：默认 220×36，开关类只有 24 高，故统一垂直居中
    Item {
        id: controlBox
        Layout.preferredWidth: root.controlWidth
        Layout.preferredHeight: 36
        Layout.alignment: Qt.AlignVCenter
    }
}
