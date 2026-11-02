"""设计令牌：颜色、间距、圆角、字体。

作为 QVariantMap 注入 QML 的 `theme` 上下文属性，全界面与所有组件共用同一套
取值，避免颜色和间距散落在各文件里。改主题只改这一处。

统一基准：浅色 + teal 强调色，QML 界面（主页面 + 设置页）全部取自此处。
层次由浅到深：background(最浅) < surface(卡片白) < surfaceHover < surfaceActive。
"""

THEME: dict = {
    # 背景层次
    "background": "#F9FAFB",
    "surface": "#FFFFFF",
    "surfaceHover": "#F3F4F6",
    "surfaceActive": "#E5E7EB",
    # 边框
    "border": "#E5E7EB",
    "borderStrong": "#D1D5DB",
    # 强调色（teal，与设置界面一致）
    "accent": "#0D9488",
    "accentHover": "#0F766E",
    "accentSoft": "#CCFBF1",
    # 文字
    "textPrimary": "#111827",
    "textSecondary": "#6B7280",
    "textMuted": "#9CA3AF",
    "textInverse": "#FFFFFF",
    # 语义色
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    # 告警/成功底色：比主色淡，用于标签背景，避免整块深背景压过正文
    "dangerSoft": "#FEF2F2",
    "successSoft": "#ECFDF5",
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
    "fontFamily": "Microsoft YaHei UI",
    "fontMono": "Cascadia Code",
}
