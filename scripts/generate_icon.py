"""生成 ContextPilot 应用图标（teal 主题，多尺寸 PNG + ICO）。

图标设计：teal(#0D9488) 圆角方块 + 白色纸飞机（发送/增强 Prompt 的意象）。
纯 QPainterPath 几何绘制，不依赖字体，16~256px 任意尺寸都清晰。
产物：
  - src/context_pilot/ui/resources/icon.png  （256px，备用/README）
  - src/context_pilot/ui/resources/icon.ico  （16/24/32/48/64/128/256，任务栏/托盘）
"""

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPixmap

RESOURCES = Path(__file__).resolve().parent.parent / "src" / "context_pilot" / "ui" / "resources"

# teal 主题色，与 theme.py 的 accent 一致
ACCENT = "#0D9488"
ACCENT_DARK = "#0F766E"

# 纸飞机轮廓（Feather "send" 图标的 24×24 坐标系）
_PLANE = QPainterPath(QPointF(22.0, 2.0))
_PLANE.lineTo(15.0, 22.0)
_PLANE.lineTo(11.0, 13.0)
_PLANE.lineTo(2.0, 9.0)
_PLANE.closeSubpath()
# 机翼折线（增强立体感的分割线）：从 (22,2) 到 (11,13)
_FOLD_LINE = (QPointF(22.0, 2.0), QPointF(11.0, 13.0))


def draw(pixmap: QPixmap) -> None:
    s = pixmap.width()
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 背景：teal 圆角方块（留 4% 外边距，圆角随尺寸缩放）
    margin = s * 0.04
    side = s - 2 * margin
    radius = s * 0.22
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ACCENT))
    painter.drawRoundedRect(margin, margin, side, side, radius, radius)

    # 纸飞机：24×24 坐标系缩放平移到背景中央（占约 56%）
    plane_span = side * 0.56
    scale = plane_span / 20.0  # 图形在 24 坐标系中跨度约 20（2~22）
    offset = margin + (side - plane_span) / 2.0 - 2.0 * scale
    painter.save()
    painter.translate(offset, offset)
    painter.scale(scale, scale)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    painter.drawPath(_PLANE)

    # 折线：用背景色细线表现机翼折叠
    fold = QPainterPath(_FOLD_LINE[0])
    fold.lineTo(_FOLD_LINE[1])
    painter.setPen(QColor(ACCENT_DARK))
    pen = painter.pen()
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(fold)
    painter.restore()

    painter.end()


def main() -> None:
    # QPixmap/QPainter 依赖 QGuiApplication，offscreen 平台也需实例
    _app = QGuiApplication.instance() or QGuiApplication([])
    RESOURCES.mkdir(parents=True, exist_ok=True)

    # 主 PNG（256px）
    png = QPixmap(256, 256)
    draw(png)
    png.save(str(RESOURCES / "icon.png"))

    # 多尺寸 ICO（Windows 任务栏/托盘按尺寸择优）
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        draw(pm)
        icon.addPixmap(pm)
    icon.pixmap(256, 256).save(str(RESOURCES / "icon.ico"), "ICO")

    print("generated:", RESOURCES / "icon.png")
    print("generated:", RESOURCES / "icon.ico")


if __name__ == "__main__":
    main()
