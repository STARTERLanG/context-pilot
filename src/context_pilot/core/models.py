"""核心数据结构。字段沿用 PRD 7.2 的 ContextItem 约定。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextItem:
    """一条进入增强上下文的材料（规则/代码/文档等）。

    ``content`` 是全文件/整段材料的正文；``snippet`` 是本次检索实际命中的
    具体片段（代码段或文本行），``line_start``/``line_end`` 标注该片段在
    文件中的行号区间（1 起）。命中片段用于「上下文检查器」点击文件时精确
    展示被选中的那几行，而非整个文件（PRD 10.2）。
    """

    id: str
    type: str
    source: str
    content: str
    relevance: float = 0.0
    priority: int = 0
    path: str | None = None
    token_cost: int = 0
    reason: str = ""  # 为何被选中，供上下文检查器展示（PRD 10.2）
    snippet: str = ""  # 命中的具体片段（可为空，表示无精确片段）
    line_start: int | None = None  # 片段起始行号（1 起）
    line_end: int | None = None  # 片段结束行号（1 起，含）


@dataclass(frozen=True)
class OutputStyle:
    """一种优化模式预设：决定「怎么优化」与「输出多长」。

    ``key`` 是稳定标识（写进 EnhanceOptions.style），``label`` 供界面展示，
    ``mode`` 决定走哪套 system prompt（task=结构化增强/生成系统提示词；
    basic=基础优化；professional=专业优化；planning=步骤化规划），
    ``description`` 是介绍文案（主页面下拉聚焦时展示完整说明），
    ``instruction`` 是附加给模型的输出约束（模式之外的可选微调），
    ``max_tokens`` 是传给模型的硬上限。

    四种内置模式职责：
    - 结构化增强（task）：把需求改写成可直接交给编码 Agent 的任务书，用于
      **生成系统提示词**。
    - 基础优化（basic）：消除模糊表达、补充关键信息，输出更清晰的提示词文本。
    - 专业优化（professional）：把泛泛而谈转为精准、具体、有针对性，添加量化标准。
    - 步骤化规划（planning）：把模糊需求分解为结构化执行步骤（角色/目标/步骤/输出）。
    """

    key: str
    label: str
    instruction: str
    max_tokens: int
    mode: str = "task"
    description: str = ""


# 预设表：四档内置优化模式。order 即下拉展示顺序。
OUTPUT_STYLES: tuple[OutputStyle, ...] = (
    OutputStyle(
        key="default",
        label="结构化增强",
        mode="task",
        instruction="",
        max_tokens=6000,
        description=(
            "把一句简短需求改写成可直接交给编码 Agent 执行的任务书："
            "锁定意图、翻译成有序步骤、只在有证据时写约束与可验证的验收标准。"
            "适合生成系统提示词或工程任务书。"
        ),
    ),
    OutputStyle(
        key="basic",
        label="基础优化",
        mode="basic",
        instruction="",
        max_tokens=6000,
        description=(
            "消除提示词中的模糊表达和歧义，补充缺失的关键信息，明确目标，"
            "让表达更清晰、更完整、更容易被理解。保持原始意图不变，"
            "直接输出优化后的提示词文本。"
        ),
    ),
    OutputStyle(
        key="professional",
        label="专业优化",
        mode="professional",
        instruction="",
        max_tokens=6000,
        description=(
            "把泛泛而谈、缺乏针对性的提示词转为精准、具体、有针对性："
            "为抽象要求添加量化标准、明确参数与范围、补充约束与执行指导。"
            "保持核心意图，直接输出精准化后的提示词。"
        ),
    ),
    OutputStyle(
        key="planning",
        label="步骤化规划",
        mode="planning",
        instruction="",
        max_tokens=6000,
        description=(
            "把模糊需求分解为结构化的执行步骤序列：设定专家角色与可衡量目标、"
            "规划关键步骤、明确输出格式与约束，输出一份可执行的增强型提示词。"
            "适合复杂、多步骤的任务。"
        ),
    ),
)

# key → 预设的快速索引，供按 style 字符串取用
STYLE_BY_KEY: dict[str, OutputStyle] = {s.key: s for s in OUTPUT_STYLES}


def style_map(styles: "list[OutputStyle] | tuple[OutputStyle, ...] | None") -> dict[str, OutputStyle]:
    """把风格预设列表转成 key → 预设的映射（空/None 时回退默认预设）。"""
    return {s.key: s for s in (styles or OUTPUT_STYLES)}


@dataclass(frozen=True)
class ContextBudget:
    """进入增强上下文的 token 预算（PRD 二十六章）。

    规则与记忆各自独立记账，互不挤占；代码类（code / knowledge / symbol）
    共享 code 预算。max_tokens 是总量上限，用于渲染阶段的兜底截断。

    放在 core 层而不用 config.ContextConfig，是为了让 Pipeline 只依赖 core
    抽象；由装配层（app.py）用 ContextConfig.as_budget() 做一次转换注入。
    """

    max_tokens: int = 6000
    rules: int = 1500
    memory: int = 1000
    code: int = 3500


@dataclass(frozen=True)
class EnhanceOptions:
    """单次增强的可调参数。

    include_context=False 表示「无项目」模式：不检索项目规则/代码/知识摘要，
    仅对原始表述做优化（对应主页面「项目」下拉的「无项目」选项）。
    style 为输出风格预设 key（见 OUTPUT_STYLES）；max_tokens 为输出长度硬上限。
    """

    max_tokens: int = 6000
    include_context: bool = True
    style: str = "default"


@dataclass(frozen=True)
class EnhancedPrompt:
    """一次增强的完整结果，供 UI 展示与写回剪贴板。

    ``budget_tokens`` 是本次实际生效的上下文预算上限（0 表示未知/未配置）。
    它由 Pipeline 填入而非 UI 猜——否则设置页改了预算，状态栏占比还是按旧值算。
    """

    original_prompt: str
    enhanced_prompt: str
    context: list[ContextItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    budget_tokens: int = 0
