import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 「快捷键」：增强热键 + 界面开关热键。
// 捕获逻辑在 SettingsModel（Qt 键码 → ctrl+shift+… 字符串），本页只负责
// 呈现与取焦点；保存前两者都必须合法且互不相同，校验在保存时统一做。
Flickable {
    id: root
    contentWidth: width
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    // 按 id 从候选列表查展示名（下拉收起态要显示「当前选中哪一项」）。
    // styles / models 的项都含 id 与 name 字段，此处统一取 name。
    function labelOf(list, id) {
        if (!list || !id) return ""
        for (var i = 0; i < list.length; i++)
            if (list[i].id === id) return list[i].name
        return ""
    }

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

        AppSectionCard {
            Text {
                Layout.fillWidth: true
                text: "全局快捷键"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "增强热键"
                desc: "读取剪贴板并生成增强提示词；点击输入框后按下组合键，Esc 取消"
                AppHotkeyField {
                    anchors.centerIn: parent
                    width: 220
                    target: "hotkey"
                    text: settings.hotkey
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "显示 / 关闭界面"
                desc: "已显示则隐藏，未显示则弹出；点击输入框后按下组合键，Esc 取消"
                AppHotkeyField {
                    anchors.centerIn: parent
                    width: 220
                    target: "toggle"
                    text: settings.toggleHotkey
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: theme.border
            }

            Text {
                Layout.fillWidth: true
                text: "两个快捷键不能相同；保存后立即重绑，若被其它程序占用会给出提示。"
                color: theme.textMuted
                font.family: theme.fontFamily
                font.pixelSize: theme.fontCaption
                wrapMode: Text.Wrap
            }
        }

        // ---------- 增强热键默认值 ----------
        AppSectionCard {
            Text {
                Layout.fillWidth: true
                text: "增强热键默认值"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSubtitle
                font.weight: Font.DemiBold
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "默认模式"
                desc: "触发增强热键时默认使用的优化模式（后台触发，与主窗口当前选择无关）"
                AppSelect {
                    anchors.centerIn: parent
                    width: 180
                    label: ""
                    options: sessionCtl.styles
                    currentId: settings.defaultStyle
                    currentText: root.labelOf(sessionCtl.styles, settings.defaultStyle)
                    emptyText: "结构化增强"
                    onSelected: (id) => settings.defaultStyle = id
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "默认模型"
                desc: "触发增强热键时默认使用的模型；留空则回落为当前选中或唯一已生效模型"
                AppSelect {
                    anchors.centerIn: parent
                    width: 180
                    label: ""
                    options: sessionCtl.models
                    currentId: settings.defaultModelId
                    currentText: root.labelOf(sessionCtl.models, settings.defaultModelId)
                    emptyText: "未指定（自动回落）"
                    onSelected: (id) => settings.defaultModelId = id
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "默认项目"
                desc: "触发增强热键时默认关联的项目，决定是否检索该项目代码作为上下文；「无项目」则仅优化文本"
                AppSelect {
                    anchors.centerIn: parent
                    width: 180
                    label: ""
                    options: sessionCtl.projects
                    currentId: settings.defaultProjectId
                    currentText: root.labelOf(sessionCtl.projects, settings.defaultProjectId)
                    emptyText: "无项目"
                    onSelected: (id) => settings.defaultProjectId = (id === "default" ? "" : id)
                }
            }

            AppFieldRow {
                Layout.fillWidth: true
                title: "自动复制粘贴"
                desc: "开启后触发热键自动全选→复制→增强→粘贴回写；关闭则仅把结果写回剪贴板"
                AppToggle {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    checked: settings.autoPaste
                    onToggled: (checked) => settings.autoPaste = checked
                }
            }
        }
    }
}
