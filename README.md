# ContextPilot

面向 AI Coding Agent 的**项目感知型 Prompt Enhancement 桌面工具**。

在 Claude Code / Codex / Gemini CLI 等 Coding Agent 与「你」之间，充当独立的
Context Engineering 层：读取项目规则与代码，把一句简短的自然语言指令
（如「修一下订单接口」）重构为项目感知、可执行、可验证的工程任务 Prompt。

**形态**：Windows 桌面客户端，系统托盘常驻 + 全局热键 `Ctrl+Shift+E` + 剪贴板集成。
单一 Python 进程，无服务端、无端口。

---

## 安装

需要 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
```

## 配置

首次运行会自动生成 `~/.context-pilot/config.toml`。默认 `provider = "stub"`，
不联网、可离线验证链路。接入真实模型时修改：

```toml
[general]
# 被增强的项目根目录；留空则用启动时的工作目录
project_root = "D:/your/project"

[llm]
provider = "openai"                      # stub | openai
base_url = "https://api.deepseek.com/v1" # 任意 OpenAI 兼容端点
api_key = "sk-..."                       # 只存在本机，不进版本库
model = "deepseek-chat"
timeout = 60.0
```

兼容 OpenAI / DeepSeek / Qwen / OpenRouter / 本地 Ollama、vLLM、LM Studio 等。

## 使用

```bash
uv run context-pilot
```

启动后常驻系统托盘，无窗口。在任意终端里写好简短指令并复制，按 `Ctrl+Shift+E`：

1. 窗口浮现，显示原始指令、增强结果、命中的项目上下文
2. 可编辑增强结果
3. 点「使用增强 Prompt」→ 写回剪贴板
4. 粘贴给原来的 Coding Agent

关闭窗口只是隐藏，退出请用托盘菜单。

## 设置界面

右键托盘图标 → **设置**，或在窗口中打开。分五个标签页：

| 标签页 | 内容 |
|--------|------|
| 通用 | 项目根目录、**全局热键**（点击后直接按下组合键捕获） |
| 模型 | 提供方、接口地址、API Key、模型名、超时 |
| 上下文 | 总预算与 rules / memory / code 三项分配 |
| 记忆 | 记忆总开关、记忆列表查看与删除 |
| 行为 | 开机自启、自动写回剪贴板、关窗最小化到托盘 |

保存后立即生效：热键会重新注册，提供方与项目根目录会重建。配置写入
`~/.context-pilot/config.toml`。

## 开发

```bash
uv run pytest                                    # 全部测试
uv run pytest tests/test_pipeline.py -v          # 单个文件
uv run pytest -k "memory" -v                     # 按名称筛选
uv run ruff check .                              # 代码检查
```

### 架构

```
ui/          PySide6 + QML：窗口、托盘、预览
platform/    全局热键、剪贴板、单实例
─ 以上为呈现层，以下为引擎层（不依赖 GUI）─
core/        编排：pipeline、ranking、models
project/     项目扫描
rules/       规则加载与匹配
retrieval/   检索（Retriever 协议 + 关键词实现）
memory/      项目记忆（SQLite）
optimizer/   Prompt 模板 + LLM 提供方
```

引擎层可在无 GUI 环境独立测试。检索器、LLM 提供方均以协议解耦，
新增实现不改动 `Pipeline`。

### 打包

```bash
pwsh scripts/build.ps1
```

> 打包脚本未经验证（需要先在开发机安装 PyInstaller 并跑一次完整构建）。

## 已知局限

- **检索基于关键词与路径匹配**，从查询中提取的是 ASCII 标识符词元。
  纯中文查询（如「修一下订单接口」）匹配不到英文代码——语义检索是后续规划。
- **项目记忆需显式写入**，自动抽取与冲突检测（PRD 8.4）尚未实现；
  设置界面可查看与删除，但不支持手动新增。
- 暂不支持 diff 视图、上下文检查器、Agent 适配器的自动写回。
- 热键捕获不覆盖方向键、翻页键等导航键（可解析但未列入可捕获键码）。

设计文档见 `ContextPilot.md`（PRD），工程规范见 `docs/engineering-standards.md`。
