# 用 PyInstaller 打包为 Windows 可执行程序。
# 依赖：uv add --dev pyinstaller
# 产物：dist/ContextPilot/ContextPilot.exe（onedir，启动比 onefile 快）

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

uv run pyinstaller `
    --noconfirm `
    --windowed `
    --name ContextPilot `
    --add-data "src/context_pilot/ui/qml;context_pilot/ui/qml" `
    --collect-all PySide6 `
    --hidden-import context_pilot.ui.app `
    src/context_pilot/__main__.py

Write-Host "完成：dist/ContextPilot/ContextPilot.exe"
