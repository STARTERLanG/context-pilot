import QtQuick
import QtQuick.Layouts
import "../components"

// 设置页：与主页面共用同一布局框架（同一张卡片、同顶栏、同内边距），
// 只替换卡片内的内容区域——叠加在同一矩形的四个分区互斥可见，切换分类不销毁
// Item，输入状态得以保留；退出设置页也不销毁本页（Loader 常驻），再次进入时
// 仍是上次离开的样子。
Item {
    id: root

    // 全局热键（系统级）与窗口快捷键（窗口内）是两套东西，各自一个分类：
    // 前者注册到 OS，后者只在窗口聚焦时生效，混在一页里解释不清。
    readonly property var tabs: ["常规", "模型配置", "项目索引", "优化模式", "全局热键", "窗口快捷键"]
    property int currentTab: 0

    // 返回主页面：由外层切换可见性；主页面期间从未被销毁，内容与状态原样回来
    signal backRequested()

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spaceMd

        // ---------- 顶部：返回 + 分类切换 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spaceMd

            // 返回按钮：图标 + 文字胶囊（与「历史记录 / 清空」同一套样式语言）
            Rectangle {
                id: backBtn
                objectName: "settingsBackBtn"
                Layout.preferredWidth: backRow.width + theme.spaceMd * 2
                Layout.preferredHeight: 28
                radius: theme.radiusFull
                color: backHover.hovered ? theme.surfaceActive : theme.surface
                border.width: 1
                border.color: theme.border

                Row {
                    id: backRow
                    anchors.centerIn: parent
                    spacing: theme.spaceXs

                    // 左箭头
                    Canvas {
                        width: 12; height: 12
                        anchors.verticalCenter: parent.verticalCenter
                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)
                            c.strokeStyle = theme.textSecondary
                            c.lineWidth = 1.4
                            c.lineCap = "round"
                            c.lineJoin = "round"
                            c.beginPath()
                            c.moveTo(width * 0.72, 2)
                            c.lineTo(2, height / 2)
                            c.lineTo(width * 0.72, height - 2)
                            c.stroke()
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "返回"
                        color: theme.textSecondary
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSmall
                    }
                }

                HoverHandler { id: backHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: root.backRequested() }

                Accessible.role: Accessible.Button
                Accessible.name: "返回主页面"
            }

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: "设置"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }

            Item { Layout.fillWidth: true }

            AppSegmented {
                Layout.alignment: Qt.AlignVCenter
                // 六个分类：收紧段宽与间距，才放得下同行的返回按钮与标题
                segmentMinWidth: 76
                segmentSpacing: 2
                options: root.tabs
                currentIndex: root.currentTab
                onActivated: (index) => root.currentTab = index
            }
        }

        // ---------- 内容：四个分区共用同一矩形 ----------
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            SettingsGeneral {
                anchors.fill: parent
                visible: root.currentTab === 0
            }
            SettingsProfiles {
                anchors.fill: parent
                visible: root.currentTab === 1
            }
            SettingsProjects {
                anchors.fill: parent
                visible: root.currentTab === 2
            }
            SettingsStyles {
                anchors.fill: parent
                visible: root.currentTab === 3
            }
            SettingsHotkey {
                anchors.fill: parent
                visible: root.currentTab === 4
            }
            SettingsShortcuts {
                anchors.fill: parent
                visible: root.currentTab === 5
            }
        }

        // ---------- 底部保存栏（与主页面底部栏同高，几何完全一致） ----------
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            spacing: theme.spaceMd

            Text {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                text: settingsCtl.message
                color: settingsCtl.messageError ? theme.danger : theme.success
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
                elide: Text.ElideRight
            }

            AppButton {
                text: "保存"
                variant: "primary"
                Layout.preferredWidth: 96
                Layout.preferredHeight: 36
                onClicked: settingsCtl.save()
            }
        }
    }
}
