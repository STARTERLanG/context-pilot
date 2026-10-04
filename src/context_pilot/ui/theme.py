"""设计令牌：颜色、间距、圆角、字体。

作为 QVariantMap 注入 QML 的 `theme` 上下文属性，全界面与所有组件共用同一套
取值，避免颜色和间距散落在各文件里。改主题只改这一处。
"""

# 深色中性灰阶 + 单一强调色。层次由深到浅：background < surface < surfaceHover。
THEME: dict = {
    # 背景层次
    "background": "#0E0F12",
    "surface": "#15171C",
    "surfaceHover": "#1B1E24",
    "surfaceActive": "#22262E",
    # 边框
    "border": "#242830",
    "borderStrong": "#343A46",
    # 强调色
    "accent": "#5B8CFF",
    "accentHover": "#6E9AFF",
    "accentSoft": "#1E2740",
    # 文字
    "textPrimary": "#ECEDEF",
    "textSecondary": "#9CA2AD",
    "textMuted": "#666C78",
    "textInverse": "#0E0F12",
    # 语义色
    "success": "#4ADE80",
    "warning": "#FBBF24",
    "danger": "#F87171",
    # 圆角
    "radiusSm": 6,
    "radiusMd": 8,
    "radiusLg": 12,
    "radiusFull": 999,
    # 间距梯度
    "spaceXs": 4,
    "spaceSm": 8,
    "spaceMd": 12,
    "spaceLg": 16,
    "spaceXl": 24,
    # 字号
    "fontCaption": 11,
    "fontSmall": 12,
    "fontBody": 13,
    "fontSubtitle": 15,
    "fontTitle": 20,
    # 字体
    "fontFamily": "Segoe UI",
    "fontMono": "Cascadia Code",
}
