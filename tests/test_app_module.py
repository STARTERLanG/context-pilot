"""ui.app 装配模块的启动前健康检查。

背景：一次重构不小心删掉了 `from context_pilot.ui.icon import app_icon` 与
`config = load_config()` 两行，而 NameError 只有**运行到那一行**时才炸——
compileall、常规单测、甚至 import 模块都发现不了（名字查找发生在调用时）。

所以这里补三道防线：
  * 导入整个包（含 ui.app），缺失的 import / 循环导入立即暴露；
  * 扫描字节码里被当作**全局**引用的名字（区别于属性名），逐个确认模块里有定义；
  * 用 pyflakes 静态检查 undefined name——本次事故的类别。
    pyflakes 属可选开发工具，没装就跳过，不影响 CI 结果。
"""

import builtins
import dis
import importlib
import importlib.util
import io
import pkgutil
import types

import pytest

import context_pilot
from context_pilot.ui import app as app_module

# 只有这些指令做「模块全局名字」查找；LOAD_ATTR / LOAD_METHOD 等是属性，不能算进来
_GLOBAL_OPS = {"LOAD_GLOBAL", "LOAD_NAME", "STORE_GLOBAL", "DELETE_GLOBAL"}


def _iter_submodules(package):
    yield package.__name__
    for info in pkgutil.walk_packages(
        package.__path__, prefix=package.__name__ + "."
    ):
        yield info.name


def _global_names(code: types.CodeType) -> set[str]:
    """递归收集一个 code object（含其嵌套函数）引用的全局名字。"""
    names: set[str] = set()
    for ins in dis.get_instructions(code):
        if ins.opname not in _GLOBAL_OPS:
            continue
        name = ins.argval
        if not isinstance(name, str):
            # 3.12 起 CALL 约定会给 LOAD_GLOBAL 加 "NULL + " 前缀，argval 可能为 None
            name = (ins.argrepr or "").replace("NULL + ", "").strip()
        if name:
            names.add(name)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            names |= _global_names(const)
    return names


def test_import_every_module():
    """包内每个模块都能独立导入（编译通过 ≠ 导入成功）。"""
    for name in _iter_submodules(context_pilot):
        importlib.import_module(name)


def test_main_entry_callable():
    """pyproject 的 console-script 指向 app:main，它必须存在且引用到图标助手。"""
    assert callable(app_module.main)
    assert app_module.app_icon is not None
    assert "app_icon" in _global_names(app_module.main.__code__)


def test_no_undefined_globals_in_app_module():
    """模块内所有顶层函数引用的全局名字都必须在模块里有定义。

    这是本次 NameError 的直接防线：删掉 import 或赋值语句都会在这里被抓住。
    """
    defined = set(app_module.__dict__) | set(dir(builtins))
    module_dict = vars(app_module)
    targets = {
        name: obj
        for name, obj in module_dict.items()
        if getattr(obj, "__globals__", None) is module_dict
        and isinstance(obj, (types.FunctionType, type))
    }
    assert targets, "没找到可检查的函数"
    for name, obj in targets.items():
        code = getattr(obj, "__code__", None) or getattr(
            getattr(obj, "__init__", None), "__code__", None
        )
        if code is None:
            continue
        missing = sorted(_global_names(code) - defined)
        assert missing == [], f"{name}() 引用了未定义的名字：{missing}"


@pytest.mark.parametrize(
    "module_name",
    ["context_pilot.ui.app", "context_pilot.ui.icon", "context_pilot.ui.tray"],
)
def test_pyflakes_reports_no_undefined_name(module_name):
    """静态检查：不得出现 undefined name（工具未安装则跳过）。"""
    pytest.importorskip("pyflakes.api")
    spec = importlib.util.find_spec(module_name)
    assert spec is not None and spec.origin is not None
    with open(spec.origin, encoding="utf-8") as handle:
        source = handle.read()
    messages = _flake(source, spec.origin)
    undefined = [str(m) for m in messages if "undefined name" in str(m)]
    assert undefined == [], f"{module_name}: {undefined}"


def _flake(source: str, filename: str) -> list:
    """跑一次 pyflakes 并收集消息对象（不打印到 stderr）。"""
    try:
        from pyflakes import api  # type: ignore[import-not-found]
        from pyflakes.reporter import Reporter  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - importorskip 已在上层挡过
        pytest.skip("pyflakes 不可用")

    class _Collector(Reporter):
        def __init__(self) -> None:
            super().__init__(io.StringIO(), io.StringIO())
            self.messages: list = []

        def flake(self, message) -> None:
            self.messages.append(message)  # 只收集，不打印

    reporter = _Collector()
    api.check(source, filename, reporter)
    return reporter.messages


def _nested_functions(node, parent_is_function=False):
    """遍历 AST，产出所有「嵌套在函数内部的函数定义」及其行号。"""
    import ast

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if parent_is_function:
                yield child
            # 该函数自身的内部仍属于「嵌套」语境
            yield from _nested_functions(child, parent_is_function=True)
        else:
            yield from _nested_functions(child, parent_is_function=parent_is_function)


def test_nested_functions_must_not_take_self():
    """`main()` 里的闭包不能以 self 作首参。

    背景：一次改动把闭包 `_run_enhance(text, ...)` 误写成
    `_run_enhance(self, text, ...)`。它只是局部函数而非方法，于是第一个位置
    实参被吞进 `self`，调用时抛 `TypeError: missing 1 required positional
    argument: 'text'`。该异常发生在 QTimer 回调里，既不进应用日志也没有任何
    UI 反馈——表现为「按了热键只闪一下进行中提示，然后彻底没反应」，极难排查。

    这类错误 pyflakes / 类型检查都发现不了（签名本身合法），只能靠静态规则拦。
    """
    import ast

    source = io.open(app_module.__file__, encoding="utf-8").read()
    tree = ast.parse(source)
    offenders = []
    for fn in _nested_functions(tree):
        args = [a.arg for a in fn.args.posonlyargs + fn.args.args]
        if args and args[0] == "self":
            offenders.append(f"{fn.name}(第 {fn.lineno} 行) 首参为 self")
    assert offenders == [], "嵌套函数误带 self 参数：" + "；".join(offenders)
