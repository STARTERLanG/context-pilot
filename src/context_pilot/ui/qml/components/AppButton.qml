import QtQuick

// 统一按钮。variant: primary(实心强调) / secondary(描边) / ghost(无底) / danger
// 注意：不声明 enabled，直接复用基类 Item.enabled，避免覆盖基类成员告警。
Rectangle {
    id: root
    property string text: ""
    property string variant: "secondary"
    signal clicked()

    implicitWidth: label.implicitWidth + theme.spaceLg * 2
    implicitHeight: 36
    radius: theme.radiusMd
    opacity: enabled ? 1.0 : 0.45
    border.width: variant === "primary" ? 0 : 1
    border.color: variant === "ghost" ? "transparent" : theme.borderStrong

    color: {
        if (!enabled) return variant === "primary" ? theme.accent : theme.surface
        if (variant === "primary") return hover.hovered ? theme.accentHover : theme.accent
        if (variant === "danger") return hover.hovered ? "#EF4444" : theme.danger
        if (variant === "ghost") return hover.hovered ? theme.surfaceHover : "transparent"
        return hover.hovered ? theme.surfaceHover : theme.surface
    }
    Behavior on color { ColorAnimation { duration: 90 } }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.variant === "primary" || root.variant === "danger"
               ? theme.textInverse : theme.textPrimary
        font.family: theme.fontFamily
        font.pixelSize: theme.fontBody
        font.weight: root.variant === "primary" ? Font.DemiBold : Font.Normal
    }

    HoverHandler {
        id: hover
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
    TapHandler {
        enabled: root.enabled
        onTapped: root.clicked()
    }
}
