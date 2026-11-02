import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 工具栏下拉框（主页面顶行「项目 / 模型」）。
// 与 AppSegmented 同处一行、同一套视觉：38 高、radiusMd、1px 边框、fontBody。
// 设置页表单里的 AppComboBox 是另一版（36 高、纯字符串 + placeholder 语义），
// 两者场景不同，故分开维护。
Item {
    id: root
    property string label: ""
    property var options: []
    property string currentId: ""
    property string currentText: ""
    property string emptyText: "暂无选项"
    // 需要用户注意时（如尚未选择增强目标）用告警色描边，把视线引到该点哪里
    property bool attention: false
    property int maximumListHeight: 240
    signal selected(string id)

    implicitWidth: 168
    implicitHeight: 38

    Rectangle {
        anchors.fill: parent
        radius: theme.radiusMd
        color: selHover.hovered ? theme.surfaceHover : theme.surface
        border.width: 1
        border.color: popup.visible ? theme.accent
                    : root.attention ? theme.warning
                    : selHover.hovered ? theme.borderStrong
                    : theme.border
        Behavior on border.color { ColorAnimation { duration: 100 } }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: theme.spaceMd
            anchors.rightMargin: theme.spaceXs
            spacing: theme.spaceXs

            Text {
                Layout.alignment: Qt.AlignVCenter
                visible: root.label.length > 0
                text: root.label
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
            }
            Text {
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
                text: root.currentText.length > 0 ? root.currentText : root.emptyText
                color: root.currentText.length > 0 ? theme.textPrimary : theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
                elide: Text.ElideRight
            }
            // 箭头：展开时转 180°，颜色同步强调色
            Canvas {
                id: chevron
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: 10
                Layout.preferredHeight: 10
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
        }

        HoverHandler { id: selHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: popup.open() }

        Accessible.role: Accessible.ComboBox
        Accessible.name: root.label.length > 0 ? root.label + "选择"
                                               : "下拉选择(" + root.currentText + ")"
    }

    // 弹层：Qt Quick Controls 的 Popup 不挂在普通父节点下（走窗口 overlay），
    // 因此不会被外层卡片的 clip 裁掉，长列表也不会顶破窗口（自身限高 + 滚动）。
    Popup {
        id: popup
        x: 0
        y: root.height + 4
        width: Math.max(root.width, 220)
        padding: 4
        height: Math.min(Math.max(root.options.length, 1) * 30 + 8, root.maximumListHeight)
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

        contentItem: ColumnLayout {
            anchors.fill: parent
            spacing: 0

            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.options.length > 0
                clip: true
                model: root.options
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { width: 6; policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    required property var modelData
                    // 选中项整行加底色 + 强调色文字 + 对勾，三重反馈：
                    // 只看一眼就能确认「当前增强用的是哪一条」，不必逐行找圆点。
                    readonly property bool isCurrent: modelData.id === root.currentId
                    width: list.width
                    height: 30
                    radius: theme.radiusSm
                    color: isCurrent ? theme.accentSoft
                         : rowHover.hovered ? theme.surfaceHover
                         : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: theme.spaceMd
                        anchors.rightMargin: theme.spaceMd
                        spacing: theme.spaceSm

                        Text {
                            Layout.alignment: Qt.AlignVCenter
                            Layout.fillWidth: true
                            text: modelData.name
                            color: isCurrent ? theme.accent : theme.textPrimary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSmall
                            font.weight: isCurrent ? Font.DemiBold : Font.Normal
                            elide: Text.ElideRight
                        }
                        // 对勾：Canvas 绘制，不依赖字体符号
                        Canvas {
                            Layout.alignment: Qt.AlignVCenter
                            Layout.preferredWidth: 12
                            Layout.preferredHeight: 12
                            visible: isCurrent
                            onPaint: {
                                var c = getContext("2d")
                                c.clearRect(0, 0, width, height)
                                c.strokeStyle = theme.accent
                                c.lineWidth = 1.6
                                c.lineCap = "round"
                                c.lineJoin = "round"
                                c.beginPath()
                                c.moveTo(2, height * 0.55)
                                c.lineTo(width * 0.42, height * 0.85)
                                c.lineTo(width - 2, height * 0.2)
                                c.stroke()
                            }
                        }
                        Text {
                            Layout.alignment: Qt.AlignVCenter
                            Layout.maximumWidth: 96
                            visible: text.length > 0
                            text: modelData.detail ?? ""
                            color: theme.textMuted
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                            elide: Text.ElideRight
                        }
                    }

                    HoverHandler { id: rowHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: {
                            popup.close()
                            root.selected(modelData.id)
                        }
                    }

                    // 聚焦（hover）时通过 ToolTip 显示完整介绍文案
                    ToolTip {
                        id: descTip
                        visible: rowHover.hovered && (modelData.description ?? "").length > 0
                        text: modelData.description ?? ""
                        delay: 350
                        width: Math.min(360, popup.width + 40)
                        contentItem: Text {
                            text: descTip.text
                            color: theme.textPrimary
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontCaption
                            wrapMode: Text.WordWrap
                        }
                        background: Rectangle {
                            radius: theme.radiusSm
                            color: theme.surface
                            border.width: 1
                            border.color: theme.borderStrong
                        }
                    }
                }
            }

            // 空态：列表为空时给出明确说明，而不是一个空弹层
            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.options.length === 0
                text: root.emptyText
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSmall
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
