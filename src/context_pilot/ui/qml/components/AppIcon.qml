import QtQuick

// 统一图标族（详见 docs/icon-design.md）。
//
// 全部图标在 24×24 虚拟网格里定义，描边随实际尺寸等比缩放，圆角线帽；
// 这样 10px、12px、14px、18px 下观感一致，不再靠每个调用点各写一套数值。
// 默认取 theme.textSecondary；调用点通过 tint 切到强调色，只换色不重绘。
//
// name 取值：
//   signal    品牌标记「圆点→短线→teal 长条」（双色，与主图标同基因）
//   spark     增强按钮用迷你版信号（单色，放实心按钮内）
//   trash / history / settings / minimize / maximize / close
//   copy / check / chevron / chevronUp / back
//
// 用法：AppIcon { width: 12; height: 12; name: "history" }
Item {
    id: root
    property string name: "check"
    property color tint: theme.textSecondary
    property color accentTint: theme.accent
    property real stroke: 1.8

    implicitWidth: 24
    implicitHeight: 24

    onNameChanged: canvas.requestPaint()
    onTintChanged: canvas.requestPaint()
    onAccentTintChanged: canvas.requestPaint()
    onStrokeChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            var c = getContext("2d")
            c.clearRect(0, 0, width, height)
            c.save()
            c.scale(width / 24, height / 24)
            c.strokeStyle = root.tint
            c.fillStyle = c.strokeStyle
            c.lineWidth = root.stroke
            c.lineCap = "round"
            c.lineJoin = "round"
            root.draw(c, root.name)
            c.restore()
        }
    }

    // signal 是双色：末段点亮为品牌 teal，其余保持主色
    function draw(c, n) {
        if (n === "signal" || n === "spark") {
            var endColor = n === "signal" ? root.accentTint : c.strokeStyle
            c.beginPath(); c.arc(6, 18, 2.6, 0, Math.PI * 2); c.fill()
            c.beginPath(); c.moveTo(10.5, 13.5); c.lineTo(13, 11); c.stroke()
            c.strokeStyle = endColor
            c.lineWidth = n === "spark" ? 3.6 : 4.2
            c.beginPath(); c.moveTo(15.5, 8.5); c.lineTo(20.5, 3.5); c.stroke()
            return
        }
        if (n === "trash") {
            c.strokeRect(6, 9, 12, 11)
            c.beginPath(); c.moveTo(4, 9); c.lineTo(20, 9)
            c.moveTo(10, 6); c.lineTo(14, 6)
            c.moveTo(10, 12); c.lineTo(10, 17)
            c.moveTo(14, 12); c.lineTo(14, 17)
            c.stroke(); return
        }
        if (n === "history") {
            c.beginPath(); c.arc(12, 12, 9, 0, Math.PI * 2)
            c.moveTo(12, 12); c.lineTo(12, 7)
            c.moveTo(12, 12); c.lineTo(16, 14)
            c.stroke(); return
        }
        if (n === "settings") {
            c.beginPath(); c.arc(12, 12, 5, 0, Math.PI * 2); c.stroke()
            for (var i = 0; i < 6; i++) {
                var a = i * Math.PI / 3
                var x = 12 + Math.cos(a) * 6.4
                var y = 12 + Math.sin(a) * 6.4
                c.beginPath()
                c.moveTo(x - Math.cos(a) * 1.7, y - Math.sin(a) * 1.7)
                c.lineTo(x + Math.cos(a) * 1.7, y + Math.sin(a) * 1.7)
                c.stroke()
            }
            c.beginPath(); c.arc(12, 12, 1.8, 0, Math.PI * 2); c.stroke()
            return
        }
        if (n === "minimize") {
            c.beginPath(); c.moveTo(4, 12); c.lineTo(20, 12); c.stroke(); return
        }
        if (n === "maximize") {
            c.strokeRect(5, 5, 14, 14); return
        }
        if (n === "close") {
            c.beginPath()
            c.moveTo(6, 6); c.lineTo(18, 18)
            c.moveTo(18, 6); c.lineTo(6, 18)
            c.stroke(); return
        }
        if (n === "copy") {
            // 前页完整矩形 + 后页露出的上边与左边（不画被遮住的右边/底边）
            c.strokeRect(9, 9, 11, 11)
            c.beginPath()
            c.moveTo(15, 5); c.lineTo(5, 5); c.lineTo(5, 15); c.lineTo(9, 15)
            c.stroke(); return
        }
        if (n === "check") {
            c.beginPath(); c.moveTo(4, 13); c.lineTo(10, 19); c.lineTo(20, 6); c.stroke(); return
        }
        if (n === "chevron") {
            c.beginPath(); c.moveTo(5, 9); c.lineTo(12, 16); c.lineTo(19, 9); c.stroke(); return
        }
        if (n === "chevronUp") {
            c.beginPath(); c.moveTo(5, 16); c.lineTo(12, 9); c.lineTo(19, 16); c.stroke(); return
        }
        if (n === "back") {
            c.beginPath()
            c.moveTo(11, 6); c.lineTo(5, 12); c.lineTo(11, 18)
            c.moveTo(5, 12); c.lineTo(20, 12)
            c.stroke(); return
        }
    }
}
