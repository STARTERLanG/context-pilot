"""生成 ContextPilot 应用图标：Signal 图形（V5+V6 结合版）。

设计（见 docs/icon-design.md）：
    白底圆角方块上，深墨色「圆点 → 短线 → 长条」沿对角线递进，
    只有最后一段"面"点亮为 teal(#0D9488)——把"一句短指令被增强成
    完整上下文"这个动作本身变成图形。前两段克制、末段点睛。

四个变体，纯 QPainter 几何绘制，不依赖字体或位图素材：
    light      浅色主图标（白底 + 深墨 + teal 末段）
    dark       深色反白版（深墨底 + 近白 + 亮 teal 末段）
    mono_light 浅色任务栏托盘版（透明底 + 深墨 + teal）
    mono_dark  深色任务栏托盘版（透明底 + 近白 + 亮 teal）
16/20px 托盘尺寸专门精简掉中间短线，只留「圆点 + 粗斜条」，避免糊成一团。

产物（写入 src/context_pilot/ui/resources/）：
    icon.png          256px 浅色主图（README / 文档用）
    icon.ico          16/24/32/48/64/128/256 浅色主图标（窗口/任务栏）
    icon_dark.ico     同尺寸深色反白版（深色主题备用）
    tray_light.png    64px 浅色托盘预览图
    tray_dark.png     64px 深色托盘预览图
    tray_light.ico    16/20/24/32 浅色任务栏托盘图标
    tray_dark.ico     16/20/24/32 深色任务栏托盘图标

ICO 为真正的多尺寸条目（内嵌 PNG，Windows Vista+ 原生支持），
不再像旧版那样只塞一张 256px 让系统缩小。
"""

from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

RESOURCES = Path(__file__).resolve().parent.parent / "src" / "context_pilot" / "ui" / "resources"

# 与 theme.py 的 accent 一致
ACCENT = "#0D9488"
# 深色底上的高亮 teal（提高对比度）
ACCENT_BRIGHT = "#2DD4BF"

INK_LIGHT = "#1A1A1A"
INK_DARK = "#F2F3F4"
BG_LIGHT = "#FFFFFF"
BORDER_LIGHT = "#E3E5E7"
BG_DARK = "#1B1C1E"
BORDER_DARK = "#33363A"

VARIANTS = ("light", "dark", "mono_light", "mono_dark")


def _paint(image: QImage, variant: str) -> None:
    """在给定 QImage 上绘制一个 Signal 图标变体。"""
    size = image.width()
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    dark = variant in ("dark", "mono_dark")
    mono = variant.startswith("mono_")
    bg = QColor(BG_DARK if dark else BG_LIGHT)
    border = QColor(BORDER_DARK if dark else BORDER_LIGHT)
    ink = QColor(INK_DARK if dark else INK_LIGHT)
    accent = QColor(ACCENT_BRIGHT if dark else ACCENT)

    # 1) 背景圆角方块（单色托盘版透明底，直接嵌在任务栏上）
    if not mono:
        margin = size * 0.04
        side = size - 2 * margin
        painter.setPen(QPen(border, max(0.8, size * 0.012)))
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(margin, margin, side, side), size * 0.23, size * 0.23)
        origin, span = margin, side
    else:
        origin, span = size * 0.08, size * 0.84

    # 2) 递进图形：在 100×100 虚拟坐标里定义，再等比缩放到图形区
    painter.save()
    painter.translate(origin, origin)
    painter.scale(span / 100.0, span / 100.0)

    # 16/20px 只留「圆点 + 粗斜条」，中间的"线"省掉——缩到最小仍清晰
    simplified = size <= 20

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    if simplified:
        # 托盘简化版：收紧到画面中心区域，两点挨得更近，16px 下更像一个整体
        dot_r = 7.5
        painter.drawEllipse(QRectF(38 - dot_r, 62 - dot_r, dot_r * 2, dot_r * 2))
        bar = (55, 45, 80, 20)
        bar_w = 15.0
    else:
        dot_r = 5.2
        painter.drawEllipse(QRectF(30 - dot_r, 70 - dot_r, dot_r * 2, dot_r * 2))
        pen = QPen(ink, 7.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(42, 58, 53, 47)
        bar = (67, 33, 84, 16)
        bar_w = 12.0

    pen = QPen(accent, bar_w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(*bar)

    painter.restore()
    painter.end()


def _png_bytes(image: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


def _write_ico(path: Path, sizes: tuple[int, ...], variant: str) -> None:
    """把每个尺寸渲染为 PNG 并封装成标准多尺寸 ICO。"""
    images = [(n, QImage(n, n, QImage.Format.Format_ARGB32_Premultiplied)) for n in sizes]
    for _, image in images:
        _paint(image, variant)

    payloads = [_png_bytes(image) for _, image in images]
    offset = 6 + 16 * len(images)
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    for (size, _), data in zip(images, payloads):
        # ICO 里 0 表示 256
        byte_size = 0 if size == 256 else size
        entries += struct.pack("<BBBBHHII", byte_size, byte_size, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + bytes(entries) + b"".join(payloads))


def _write_png(path: Path, size: int, variant: str) -> None:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    _paint(image, variant)
    image.save(str(path), "PNG")


def main() -> None:
    # QImage/QPainter 是纯绘制类，无需 QGuiApplication（无 GUI 事件循环也能生成）
    RESOURCES.mkdir(parents=True, exist_ok=True)

    main_sizes = (16, 24, 32, 48, 64, 128, 256)
    tray_sizes = (16, 20, 24, 32)

    _write_png(RESOURCES / "icon.png", 256, "light")
    _write_ico(RESOURCES / "icon.ico", main_sizes, "light")
    _write_ico(RESOURCES / "icon_dark.ico", main_sizes, "dark")

    _write_png(RESOURCES / "tray_light.png", 64, "mono_light")
    _write_png(RESOURCES / "tray_dark.png", 64, "mono_dark")
    _write_ico(RESOURCES / "tray_light.ico", tray_sizes, "mono_light")
    _write_ico(RESOURCES / "tray_dark.ico", tray_sizes, "mono_dark")

    for name in (
        "icon.png", "icon.ico", "icon_dark.ico",
        "tray_light.png", "tray_dark.png", "tray_light.ico", "tray_dark.ico",
    ):
        print("generated:", RESOURCES / name)


if __name__ == "__main__":
    main()
