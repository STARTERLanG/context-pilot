# 工程标准参考手册

> 本文件是项目参考手册，按需查阅。日常约束见根目录 `CLAUDE.md` 和 `.claude/rules/`。
> 使用方式：`@docs/engineering-standards.md` 引用具体章节，不要全量加载。
>
> **形态前提**：ContextPilot 是 Windows 桌面客户端（PySide6 / Qt），单一 Python 进程，
> 无服务端、无端口、无 REST。本手册按桌面应用组织，不含 Web 后端专属规范。

---

## 一、目录结构

```
project-root/
├── src/
│   └── context_pilot/
│       ├── ui/           # PySide6 窗口、托盘、QML —— 呈现层
│       ├── platform/     # 全局热键、剪贴板、单实例（Windows 优先）
│       ├── core/         # enhancer / context / ranking / pipeline 编排
│       ├── project/      # scanner / structure / git / detector
│       ├── rules/        # 规则加载与匹配
│       ├── retrieval/    # ripgrep / ast / embedding
│       ├── memory/       # store / extractor / retriever
│       ├── optimizer/    # prompt / templates / provider
│       └── adapters/     # claude / codex / gemini
├── tests/                # 镜像 src/ 结构
│   ├── conftest.py
│   ├── test_core/
│   ├── test_retrieval/
│   ├── test_rules/
│   └── factories/
├── docs/
├── scripts/              # 打包（PyInstaller）、构建
├── .env.example
├── pyproject.toml
└── README.md
```

**新增文件时的判断顺序**：先判断属于哪一层（engine / ui / platform），再判断是否需要独立文件。
单个工具函数不超过 20 行且只被一处调用时，不单独建文件。

**关键约束**：`core/` 及以下（引擎层）**不得 import `ui/` 或 `platform/`**。引擎是纯逻辑，
可在无 GUI 环境下跑测试与脚本调用。

---

## 二、依赖管理

| 场景          | 工具       | 命令                       |
| ------------- | ---------- | -------------------------- |
| Python 环境   | uv         | `uv sync` / `uv add <pkg>` |
| 生产/开发依赖 | 严格分离   | dev 依赖加 `--dev`         |

**引入新依赖的判定标准**：
1. 标准库能否解决？能则不用第三方。
2. 项目已有依赖能否解决？能则不新增。
3. 以上都不行，先向用户说明理由，等确认后再装。

**GUI 依赖特别注意**：PySide6 体积大，不得为单个小功能引入第二套 UI 栈（如再引 Flet / pywebview）。
打包工具（PyInstaller 等）放 dev 依赖。

---

## 三、测试规范

### 测试金字塔

```
    E2E / UI 冒烟   少量，覆盖唤起→增强→剪贴板闭环
    集成测试        中等，引擎 pipeline 端到端
    单元测试        大量，独立函数/模块
```

引擎层（`core/` 及以下）必须可在**无 GUI 环境**下测试，不依赖 QApplication。

### 必测场景矩阵

| 场景      | 必须覆盖 | 示例                              |
| --------- | -------- | --------------------------------- |
| 正常路径  | ✅        | 有效输入 → 预期输出               |
| 边界值    | ✅        | 空字符串、0、负数、超长路径       |
| 异常输入  | ✅        | 错误类型、越界值、恶意项目文本    |
| 并发/竞态 | 按需     | 索引读写、缓存访问                |
| 超时/重试 | 按需     | LLM API、ripgrep 子进程           |

### 覆盖率目标

| 模块                       | 最低 | 说明                     |
| -------------------------- | ---- | ------------------------ |
| core / optimizer           | 80%  | 核心编排与生成           |
| retrieval / rules / memory | 80%  | 纯逻辑，必须覆盖         |
| project / adapters         | 70%  | 外部依赖多，用 factory   |
| ui / platform              | 按需 | 冒烟测试为主，不强求覆盖 |

### 测试命名

格式：`test_<被测函数>_<场景>_<预期结果>`

```python
def test_enhance_empty_prompt_raises_value_error():
    """空 prompt 直接报错，不调用 LLM"""
```

### Mock 路径规则

```python
# ✅ patch 原始定义位置
with patch("context_pilot.retrieval.ripgrep.subprocess.run"):
    ...

# ❌ patch 本地导入引用 — 不生效
from context_pilot.retrieval.ripgrep import search
with patch("my_module.search"):
    ...
```

---

## 四、桌面应用约束

### 线程模型（最重要）

GUI 主线程**不得阻塞**。增强、检索、索引、LLM 调用一律放工作线程或异步任务，
通过信号/槽回主线程更新界面。

```
主线程 (Qt Event Loop)         工作线程 (QThread / asyncio)
  热键触发 ──────────────────▶ 读取剪贴板 → 检索 → LLM 增强
  接收信号 ◀────────────────── 完成信号
  更新窗口
```

- 禁止在 UI 回调里做 IO、subprocess、网络请求。
- 长任务必须有进度反馈与取消路径。
- 单实例：启动时用 `platform/single_instance.py` 确保只有一个进程，二次启动唤起已有窗口。

### 全局热键与剪贴板

- 热键注册失败（被占用）必须提示用户并可改键，禁止静默失败。
- 剪贴板读写遵循「读原内容 → 增强 → 写回」，不得覆盖用户未预期替换的内容。

### 配置与密钥

- API Key 存于 `~/.context-pilot/config.toml`，**禁止**硬编码、禁止提交 Git。
- 默认排除敏感文件（`.env*` / `*.pem` / `*.key` / `credentials.*` / `secrets.*`），见 PRD 第三十三章。

---

## 五、架构分层

```
ui / platform        窗口、托盘、热键、剪贴板 —— 只调用 Engine
Core (pipeline)      编排：enhance / context / ranking
Engine 模块          project / rules / retrieval / memory / optimizer
Adapters             与 Claude / Codex / Gemini 对接（剪贴板 / stdin）
Database             本地 SQLite（~/.context-pilot/<project-hash>/）
```

**依赖方向**：`ui → core → engine → adapters`，引擎层不反向依赖 UI。

**跨层规则**：
- 引擎层不依赖任何 Qt / 界面代码，Domain 与框架解耦。
- 同层之间通过 Core 编排协调，不直接互相调用。
- Adapters 只做「读入 / 写出」，不含业务逻辑。

**SOLID 优先级**（冲突时按此顺序取舍）：
1. SRP 单一职责
2. OCP 开闭原则
3. DIP 依赖倒置
4. ISP 接口隔离
5. LSP 里氏替换

---

## 六、Git 工作流

### Commit 格式

```
<type>(<scope>): <简短描述>
```

**type**：`feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `style` / `perf`

**scope**：`core` / `engine` / `ui` / `retrieval` / `rules` / `adapters` / `db`

**规则**：标题 ≤ 72 字符，中文书写，描述做了什么而非怎么做。

```
feat(ui): 添加系统托盘与全局热键唤起
fix(retrieval): 修复 ripgrep 子进程在含空格路径下失败
refactor(engine): 抽离上下文排序权重为配置
```

### 分支策略

```
main/master       生产就绪
  └── dev         集成分支（小项目可省）
       ├── feat/xxx
       ├── fix/xxx
       └── chore/xxx
```

分支名全小写，单词用 `-` 分隔。一个分支只做一件事，合并后立即删除。

### 禁止事项

- force push 到 main/master
- 跳过 Git hooks（`--no-verify`）
- 提交 `.env`、密钥文件、二进制文件、IDE 配置
- 提交构建产物（`dist/` / `build/` / `*.spec`）
- 一个大 PR 包含 10+ 个无关文件
- 提交含未解决 merge conflict 标记的文件

---

## 七、命令速查

| 操作         | 命令                                                |
| ------------ | --------------------------------------------------- |
| 安装依赖     | `uv sync`                                           |
| 添加依赖     | `uv add <package>`                                  |
| 代码检查     | `uv run ruff check .`                               |
| 自动修复     | `uv run ruff check . --fix`                         |
| 代码格式化   | `uv run ruff format .`                              |
| 运行测试     | `uv run pytest`                                     |
| 带覆盖率     | `uv run pytest --cov=src --cov-report=term-missing` |
| 单个测试文件 | `uv run pytest tests/test_xxx.py -v`                |
| 按名称筛选   | `uv run pytest -k "test_create" -v`                 |
| 启动应用     | `uv run context-pilot`                              |
| 打包         | `uv run pyinstaller ...`（scripts/ 内脚本封装）     |

---

## 八、已迁移到上层文件的内容

以下内容不再在本文件中重复，见对应文件：

| 内容                                       | 位置                               |
| ------------------------------------------ | ---------------------------------- |
| 语言与命名约定                             | `CLAUDE.md` → 项目特有约束         |
| 安全红线、输入校验、OWASP 对应项           | `.claude/rules/security.md`        |
| 异常捕获、异常链、日志规范                 | `.claude/rules/error-handling.md`  |
| 停止条件、冲突处理、预算超支               | `.claude/rules/stop-conditions.md` |
| 思考先于编码、简单优先、外科手术式修改     | `CLAUDE.md` → 强制规则             |
| 代码格式、函数长度、魔法数字等通用质量规则 | 由 ruff 自动执行，无需文档化       |

---

*版本：4.0 | 定位：桌面客户端参考手册，按需加载*
