# 用 PyInstaller 打包为 Windows 可执行程序。
# 依赖：uv add --dev pyinstaller
# 产物：dist/ContextPilot/ContextPilot.exe（onedir，启动比 onefile 快）
# --icon 决定 exe 自身与任务栏图标；resources 必须作为数据打包，否则
# 运行时 importlib.resources 找不到图标，窗口/托盘会退回程序化兜底图标。

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

uv run pyinstaller `
    --noconfirm `
    --windowed `
    --name ContextPilot `
    --icon "src/context_pilot/ui/resources/icon.ico" `
    --add-data "src/context_pilot/ui/qml;context_pilot/ui/qml" `
    --add-data "src/context_pilot/ui/resources;context_pilot/ui/resources" `
    --collect-all PySide6 `
    --hidden-import context_pilot.ui.app `
    src/context_pilot/__main__.py

Write-Host "完成：dist/ContextPilot/ContextPilot.exe"
