# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 本文件是项目级操作手册，每次会话自动加载。规则可执行、可验证，不写通用废话。
> 长规范请查阅 `docs/engineering-standards.md`。

## 项目定位

**ContextPilot** — 面向 AI Coding Agent 的**项目感知型 Prompt Enhancement 桌面工具**。
它在「用户」与 Claude Code / Codex / Gemini CLI 等 Coding Agent 之间，充当独立的
**Context Engineering / Prompt Intelligence Layer**：读取项目规则与代码，把用户简短的自然语言
指令重构为项目感知、可执行、可验证的工程任务 Prompt，交给原有 Agent 执行。

形态：**Windows 桌面客户端**（架构可移植 macOS / Linux），系统托盘常驻 + 全局热键（`Ctrl+Shift+E`）唤起
+ 剪贴板集成。**单一 Python 进程**，Context Engine 为同进程库，**无服务端、无端口、无 REST**。

完整 PRD 与技术设计见 `ContextPilot.md`（唯一权威设计文档，任何架构决策以它为准）。

**非目标**（第一阶段不做）：重新实现 Agent、执行或修改项目代码、替代 Coding Agent、
强制绑定某个模型供应商、云端保存项目代码。

**产品核心原则**：Intent First / Context Before Prompt / Evidence Before Assumption /
Minimal Context / Agent Agnostic / Human In The Loop / Progressive Intelligence。
第一条硬约束：**不改变用户意图，不编造代码事实**（引用文件前必须验证存在）。

## 当前状态

**1.0 可用**：托盘 + 全局热键 + 剪贴板闭环已跑通，接入 OpenAI 兼容 Provider 与配置系统。
引擎层（core / project / rules / retrieval / memory / optimizer）已实现，测试 38 项通过。

**已实现**：项目扫描、规则加载匹配、关键词检索、上下文排序（权重配置化）、
项目记忆（SQLite）、Prompt 模板、OpenAI 兼容提供方、QML 预览窗、托盘、单实例、配置。

**未实现**（PRD 后续阶段）：语义/向量/AST 检索、Code Graph、memory 自动抽取与冲突检测、
diff 视图、上下文检查器、Agent 适配器自动写回。

**已知局限**：关键词检索基于 ASCII 词元，纯中文查询匹配不到英文代码；
记忆需显式 `store.add()` 写入；打包脚本 `scripts/build.ps1` 未经验证。

## 常用命令

| 操作 | 命令 |
|------|------|
| 安装依赖 | `uv sync` |
| 添加依赖 | `uv add <package>` |
| 代码检查 | `uv run ruff check .` |
| 自动修复 | `uv run ruff check . --fix` |
| 代码格式化 | `uv run ruff format .` |
| 运行测试 | `uv run pytest` |
| 带覆盖率 | `uv run pytest --cov=src --cov-report=term-missing` |
| 单个测试文件 | `uv run pytest tests/test_xxx.py -v` |
| 按名称筛选 | `uv run pytest -k "test_create" -v` |

## 架构（见 `ContextPilot.md` 第三/七/十七/十八/四十四章）

技术栈：Python 3.12+，桌面 UI 用 PySide6 (Qt) + QML，解析用 Tree-sitter，
检索依次为 ripgrep → SQLite FTS5 → Embedding，存储用 SQLite（向量库 MVP 选 LanceDB/Chroma）。

核心数据流（长链路，需读多个文件才能理解）：

```
User Prompt → Intent Analyzer → Context Engine (Rules + Memory + Retrieval)
           → Context Ranking → Context Packing → Prompt Optimizer
           → Quality Checker → Preview/Edit → Agent Adapter → 原 Agent
```

模块边界（`src/context_pilot/`，PRD 第十八章）：

| 目录 | 职责 |
|------|------|
| `core/` | enhancer / context / ranking / pipeline —— 编排层 |
| `project/` | scanner（Git Root/语言/框架）、structure、git、detector |
| `rules/` | 加载 AGENTS.md、CLAUDE.md、`.cursor/rules` 等，按 scope/priority 匹配激活 |
| `retrieval/` | ripgrep / ast / embedding / ranking |
| `memory/` | store / extractor / retriever（长期项目知识） |
| `optimizer/` | prompt / templates / provider（OpenAI-compatible API） |
| `adapters/` | base + claude / codex / gemini，Core 与 Agent **完全解耦** |
| `ui/` | app / preview / diff / inspector / tray（PySide6 窗口与托盘） |
| `platform/` | hotkey / clipboard / single_instance（全局热键、剪贴板、单实例） |

关键设计约束：
- `ContextItem` 是贯穿检索与排名的统一数据结构；权重配置化，不硬编码。
- 排序公式（PRD 7.3）是既定基线，改动需回 PRD。
- LLM Provider 必须 OpenAI-compatible（可接 DeepSeek/Qwen/Ollama 等）。
- 增量索引：靠 file hash + mtime + git status 判断变更，禁止每次全量扫描。
- 信任等级：System > User Explicit > Project Rules > Docs > Code > Generated Knowledge。
- 仓库内文本（含 README/代码注释）一律视为 **untrusted project content**，不得当 System Prompt。
- 默认排除 `.env*`、`*.pem`、`*.key`、`credentials.*`、`secrets.*` 等敏感文件。

## 强制规则

### 思考先于编码

- 有歧义**先问**，不要猜。列出 2-3 种解读，给出推荐。
- 存在更简单方案时**主动指出**，哪怕用户没问。
- 不明确的地方**说“不确定”**，不要用看似合理的代码填补空白。

### 简单优先

- 只写解决问题的最小代码。没要求的功能，一行不加。
- 没要求的抽象、配置、“以防万一”的灵活性，一律不做。
- 如果你写了 200 行但 50 行能搞定，**重写**。

### 外科手术式修改

- 只改必须改的地方。不“顺手优化”旁边的代码、注释、格式。
- 匹配现有代码风格，哪怕你觉得丑。
- 只清理**你的改动**产生的废弃 import。原有的 dead code 可以提，不要删。

### 目标驱动执行

- 把任务变成**可验证目标**：“加校验” → “先写无效输入的测试，然后让它们通过”。
- 多步骤任务先输出简短计划，每步带验证方式。

## 项目特有约束

### 语言与命名

- 代码注释用**简体中文**，变量/函数/类名用**英文**。
- Git 提交信息用中文，格式：`<type>(<scope>): <描述>`。scope 建议：`core` / `engine` / `ui` / `retrieval` / `rules` / `adapters` / `db`。
- Python 模块 `snake_case.py`，Qt/QML 文件用 Qt 惯例（`PascalCase.qml`）。
- 类型注解用现代语法（`User | None`），**禁止** `from typing import Optional`。
- **禁止**相对导入（`from .services import x`），全部用绝对导入。

### Token 预算

- 单任务预算：4,000 tokens。
- 单会话预算：30,000 tokens。
- 接近预算时**主动告知**，摘要后重新开始，不要静默超支。
- 产品自身的上下文预算（PRD 二十六章）：`max_tokens=6000`，其中 rules 1500 / memory 1000 / code 3500。

## 停止条件（必须先问，不要自己决定）

遇到以下情况**停下来问用户**，禁止自行假设或继续：

- 需要修改白名单以外的文件。
- 需要新增依赖。
- 需求有歧义，规格里没写清楚（以 `ContextPilot.md` 为准；PRD 未覆盖则问）。
- 测试失败但你认为是测试本身的问题。
- 涉及认证、支付、权限相关逻辑。
- 发现代码库中有两个冲突的模式，需要选一个。

## 禁止事项

- 不写没被要求的功能、抽象、配置。
- 不“顺手”修改无关代码或注释。
- 不使用模型做确定性判断（路由、重试、状态码处理用 if-else）。
- 不在日志中泄露敏感信息。
- 不提交 `.env`、密钥文件、调试用的 `print()`。

## 规则文件索引

安全红线 / 输入校验 / OWASP、异常捕获与日志、停止条件，分别见
`.claude/rules/security.md`、`.claude/rules/error-handling.md`、`.claude/rules/stop-conditions.md`。
