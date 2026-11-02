import QtQuick
import QtQuick.Layouts

// 录入型表单行：字段名固定 96px 右对齐 + 控件铺满剩余宽度（长 URL / Key 不被压缩）。
// 与 AppFieldRow 区分：后者是「左说明 + 右固定宽控件」的开关型表单。
RowLayout {
    id: root
    property string label: ""
    property int labelWidth: 96
    default property alias control: controlBox.data

    spacing: theme.spaceMd

    Text {
        Layout.preferredWidth: root.labelWidth
        Layout.alignment: Qt.AlignVCenter
        text: root.label
        color: theme.textSecondary
        font.family: theme.fontFamily
        font.pixelSize: theme.fontSmall
        horizontalAlignment: Text.AlignRight
    }

    Item {
        id: controlBox
        Layout.fillWidth: true
        Layout.preferredHeight: 36
        Layout.alignment: Qt.AlignVCenter
    }
}
