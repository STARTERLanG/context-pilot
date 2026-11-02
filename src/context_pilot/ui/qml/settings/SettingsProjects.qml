import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「项目索引」：添加本地文件夹路径并手动触发索引。
// 增删改由 settingsCtl（Python）落到 SQLite，状态文案在控制层统一中文化。
Flickable {
    id: root
    contentWidth: width
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ScrollBar.vertical: ScrollBar {
        width: 6
        policy: ScrollBar.AsNeeded
        contentItem: Rectangle {
            radius: 3
            color: parent.pressed ? theme.accentHover
                 : parent.hovered ? theme.accent
                 : theme.borderStrong
            opacity: parent.active || parent.hovered || parent.pressed ? 1.0 : 0.6
        }
    }

    ColumnLayout {
        id: column
        width: root.width
        spacing: theme.spaceLg

        // ---------- 添加卡片 ----------
        AppSectionCard {
            Column {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    width: parent.width
                    text: "添加项目"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: "添加本地文件夹路径，手动触发索引；状态实时展示"
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSmall
                    wrapMode: Text.Wrap
                }
            }

            AppFormRow {
                Layout.fillWidth: true
                label: "路径"
                AppTextField {
                    id: pathField
                    anchors.centerIn: parent
                    width: parent.width
                    placeholderText: "D:/your/project（绝对路径）"
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "添加"
                    variant: "primary"
                    Layout.preferredWidth: 88
                    Layout.preferredHeight: 36
                    onClicked: {
                        if (settingsCtl.addProject(pathField.text)) {
                            pathField.text = ""
                        }
                    }
                }
            }
        }

        // ---------- 列表卡片 ----------
        AppSectionCard {
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "已添加项目"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "共 " + settingsCtl.projects.length + " 个"
                    color: theme.textMuted
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontCaption
                }
            }

            // 空态
            Text {
                Layout.fillWidth: true
                visible: settingsCtl.projects.length === 0
                text: "暂无项目，请在上方添加文件夹路径"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontBody
                horizontalAlignment: Text.AlignHCenter
            }

            Repeater {
                model: settingsCtl.projects
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: theme.spaceXs

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spaceMd

                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                width: parent.width
                                text: modelData.name + "  [" + modelData.statusText + "]"
                                color: theme.textPrimary
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontSmall
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: modelData.path
                                color: theme.textMuted
                                font.family: theme.fontMono
                                font.pixelSize: theme.fontCaption
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                visible: modelData.error.length > 0
                                text: modelData.error
                                color: theme.danger
                                font.family: theme.fontFamily
                                font.pixelSize: theme.fontCaption
                                elide: Text.ElideRight
                            }
                        }

                        AppButton {
                            text: modelData.status === "running" ? "创建中…" : "创建索引"
                            variant: "secondary"
                            enabled: modelData.status !== "running"
                            Layout.preferredWidth: 88
                            Layout.preferredHeight: 32
                            onClicked: settingsCtl.buildIndex(modelData.id)
                        }
                        AppButton {
                            text: "删除"
                            variant: "danger"
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 32
                            onClicked: settingsCtl.deleteProject(modelData.id)
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: theme.border
                    }
                }
            }
        }
    }
}
