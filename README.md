<div align="center">

# ContextPilot

**面向 AI Coding Agent 的项目感知型 Prompt 增强桌面工具**

在 Claude Code / Codex / Gemini CLI 等 Coding Agent 与你之间，充当独立的
**Context Engineering 层**：读取项目规则与代码，把一句简短的自然语言指令
（如「修一下订单接口」）重构为项目感知、可执行、可验证的工程任务 Prompt。

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.0.1-blue)](https://github.com/yourname/context-pilot/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows)](https://www.microsoft.com/windows)

</div>

---

## 简介

ContextPilot 是一个 **Windows 桌面客户端**，以系统托盘常驻 + 全局热键
<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> + 剪贴板集成的方式运行。
单一 Python 进程，无服务端、无端口，模型调用全部发生在本地。

它的核心价值在于：你不需要把项目的规则、结构、上下文手动塞进每一句指令，
ContextPilot 会自动完成这一层工程化，让 Coding Agent 收到的是「理解项目」之后的
增强 Prompt。

## 核心功能

- **项目感知增强** — 读取项目规则、代码结构与记忆，把自然语言指令重构为结构化工程任务
- **多模型支持** — 兼容 OpenAI / DeepSeek / Qwen / OpenRouter，以及本地 Ollama、vLLM、LM Studio
- **多套配置切换** — 多套模型配置可勾选「生效」，主界面下拉随时切换增强目标
- **全局热键** — 任意终端复制指令后一键唤起，增强结果自动写回剪贴板
- **四档优化模式** — 结构化增强 / 基础优化 / 专业优化 / 步骤化规划
- **项目索引与记忆** — 本地项目扫描 + SQLite 记忆，模型配置与密钥只存本机

## 安装

### 环境要求

- **Windows 10/11**
- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)**（推荐的包管理与运行工具）

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourname/context-pilot.git
cd context-pilot

# 2. 安装依赖
uv sync

# 3. 启动
uv run context-pilot
```

启动后程序常驻系统托盘（无窗口）。首次运行会自动生成配置文件
`~/.context-pilot/config.toml`。

> **Windows 代码完整性提示**：若 `uv` 生成的 console-script exe 被 Smart App
> Control 拦截（`os error 4551`），可用仓库内的 `run.cmd` 直接以 venv 的 Python
> 运行模块绕过该问题。

## 快速上手

1. 在任意终端里写下一句简短指令，例如：

   ```
   修一下订单接口的越权校验
   ```

2. 复制它，按下全局热键 <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd>

3. 弹出的窗口会展示：**原始指令**、**增强结果**、**命中的项目上下文**

4. 可编辑增强结果，点击「使用增强 Prompt」写回剪贴板

5. 把增强后的 Prompt 粘贴给你的 Coding Agent

> 关闭窗口只是隐藏；彻底退出请使用托盘菜单。

## 配置

### 配置文件

首次运行生成 `~/.context-pilot/config.toml`，当前只保留调用超时：

```toml
[llm]
timeout = 60.0
```

### 模型配置

模型的 **Base URL / API Key / 模型名** 不在配置文件里，而在 **设置页 → 模型配置**
中维护，存入 `~/.context-pilot/profiles.db`（Key 仅存本机）。

| 概念 | 含义 |
|------|------|
| **生效**（设置页勾选） | 决定哪些模型配置出现在主页面的「模型」下拉，可多选 |
| **增强目标**（主页面下拉） | 决定本次增强调用哪一套；多条生效时需手动选择 |

选定的增强目标会记住并在下次启动沿用；被停用或删除时自动回落到可用配置。
没有任何已生效配置时，增强入口会置灰并提示去设置页勾选。

> 旧版 `config.toml` 中的 `provider` / `base_url` / `api_key` / `model` 已废弃，
> 读取时忽略、下次保存时自动移除。

### 设置界面

主窗口右上角齿轮图标进入设置页，共六个标签页：

| 标签页 | 内容 |
|--------|------|
| 常规 | 上下文预算、开机自启、自动写回剪贴板、关窗最小化 |
| 模型配置 | 多套 OpenAI 兼容配置的新增 / 编辑 / 删除 / 连通性测试 / 生效勾选 |
| 项目索引 | 添加本地文件夹并手动触发索引，状态实时展示 |
| 优化模式 | 四档优化模式的增删改 |
| 全局热键 | 增强热键与显示 / 关闭界面切换热键 |
| 窗口快捷键 | 窗口内动作的预设方案 + 逐条自定义 |

## 目录结构

```
.
├── src/context_pilot/          # 主源码
│   ├── ui/                     # PySide6 + QML：窗口、托盘、预览
│   │   └── qml/                # QML 界面与组件
│   ├── platform/               # 全局热键、剪贴板、单实例
│   ├── core/                   # 编排：pipeline、ranking、models
│   ├── project/                # 项目扫描
│   ├── rules/                  # 规则加载与匹配
│   ├── retrieval/              # 检索（Retriever 协议 + 关键词实现）
│   ├── memory/                 # 项目记忆（SQLite）
│   ├── optimizer/              # Prompt 模板 + LLM 提供方
│   └── graph/                  # 代码图构建与检索
├── tests/                      # 单元测试
├── scripts/                    # 构建与资源生成脚本
├── pyproject.toml              # 项目元数据与依赖
└── uv.lock                     # 锁定的依赖版本
```

> 呈现层（`ui/`、`platform/`）与引擎层（其余模块）解耦，引擎层可在无 GUI 环境
> 独立测试。检索器、LLM 提供方均以协议解耦，新增实现不改动 `Pipeline`。

## 开发

```bash
uv run pytest                                # 全部测试
uv run pytest tests/test_pipeline.py -v      # 单个文件
uv run pytest -k "memory" -v                 # 按名称筛选
uv run pyflakes src/ context_pilot/           # 静态检查未定义名
```

### 打包

```bash
pwsh scripts/build.ps1
```

> 打包脚本需先在开发机安装 PyInstaller 并跑一次完整构建验证。

## 已知局限

- **检索基于关键词与路径匹配**，纯中文查询（如「修一下订单接口」）暂无法匹配英文
  代码标识符，语义检索为后续规划方向
- **项目记忆需显式写入**，自动抽取与冲突检测尚未实现
- **Agent 适配器的自动写回**尚未实现（剪贴板模式已可用）
- **热键捕获**不覆盖方向键、翻页键等导航键

## 许可证

本项目采用 [MIT License](LICENSE)。

## 致谢

灵感与部分设计参考自各类 Context Engineering 实践与 Coding Agent 生态。
