import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    width: 760
    height: 620
    color: "#17181b"

    // 外层 Rectangle 是 QQuickView 的根对象，窗口关闭走 model.close()
    // 而不是隐藏根对象，避免破坏 QQuickView 的复用。

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "ContextPilot"
                color: "#e8eaed"
                font.pixelSize: 20
                font.bold: true
                Layout.fillWidth: true
            }
            Text {
                text: preview.status
                color: "#8b93a1"
                font.pixelSize: 13
            }
        }

        Text {
            text: "原始 Prompt"
            color: "#8b93a1"
            font.pixelSize: 12
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: "#21232a"
            radius: 8
            ScrollView {
                anchors.fill: parent
                anchors.margins: 10
                TextArea {
                    id: originalArea
                    text: preview.originalPrompt
                    color: "#c8cdd6"
                    readOnly: true
                    wrapMode: TextArea.Wrap
                    background: null
                }
            }
        }

        Text {
            text: "增强结果（可编辑）"
            color: "#8b93a1"
            font.pixelSize: 12
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#21232a"
            radius: 8
            ScrollView {
                anchors.fill: parent
                anchors.margins: 10
                TextArea {
                    id: enhancedArea
                    text: preview.enhancedPrompt
                    color: "#e8eaed"
                    wrapMode: TextArea.Wrap
                    selectByMouse: true
                    background: null
                }
            }
        }

        Text {
            text: "上下文"
            color: "#8b93a1"
            font.pixelSize: 12
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: contextColumn.implicitHeight + 20
            color: "#21232a"
            radius: 8
            Column {
                id: contextColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: 10
                spacing: 4
                Repeater {
                    model: preview.contextFiles
                    Text {
                        required property string modelData
                        text: "· " + modelData
                        color: "#9aa3b2"
                        font.pixelSize: 12
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Item { Layout.fillWidth: true }
            Button {
                text: "取消"
                onClicked: preview.close()
            }
            Button {
                text: "使用增强 Prompt"
                highlighted: true
                onClicked: preview.use(enhancedArea.text)
            }
        }
    }
}
