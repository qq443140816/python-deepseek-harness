"""子代理委派工具单元测试。"""

from __future__ import annotations

from pathlib import Path

from pdsh.config import Settings
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ToolCall
from pdsh.session.store import SessionStore
from pdsh.subagent import SubagentTool
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.base import ToolContext, ToolRegistry
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore


def _registry_with_subagent(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
    llm: MockLLM,
) -> ToolRegistry:
    registry = build_default_registry(settings, ask_manager, todo_store)
    registry.register(SubagentTool(llm, registry))
    return registry


async def test_subagent_returns_conclusion(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
    store: SessionStore,
) -> None:
    llm = MockLLM(
        [
            # 主循环第一步：委派子代理
            MockStep(
                tool_calls=[
                    ToolCall(
                        id="s1",
                        name="subagent",
                        arguments={"task": "统计工作区文件"},
                    )
                ]
            ),
            # 子代理内部第一步：直接给出结论
            MockStep(text="子代理结论：共 3 个文件"),
            # 主循环收尾
            MockStep(text="任务完成"),
        ]
    )
    registry = _registry_with_subagent(settings, ask_manager, todo_store, llm)
    tool = registry.get("subagent")
    assert isinstance(tool, SubagentTool)
    context = ToolContext(workspace=str(settings.workspace), session_id=1, actor="test")
    result = await tool.run({"task": "统计工作区文件"}, context)
    assert result.is_error is False
    assert "子代理结论" in result.output


async def test_subagent_inner_tools_restricted(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
) -> None:
    llm = MockLLM()
    registry = _registry_with_subagent(settings, ask_manager, todo_store, llm)
    tool = registry.get("subagent")
    assert isinstance(tool, SubagentTool)
    inner_names = tool._inner.names()  # noqa: SLF001
    assert "ask_user" not in inner_names
    assert "subagent" not in inner_names
    assert "todo_write" not in inner_names
    assert "fs_read" in inner_names


async def test_subagent_uses_tools_then_concludes(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
) -> None:
    (Path(settings.workspace) / "data.txt").write_text("42", encoding="utf-8")
    llm = MockLLM(
        [
            MockStep(
                tool_calls=[
                    ToolCall(
                        id="r1",
                        name="fs_read",
                        arguments={"path": "data.txt"},
                    )
                ]
            ),
            MockStep(text="文件内容是 42"),
        ]
    )
    registry = build_default_registry(settings, ask_manager, todo_store)
    tool = SubagentTool(llm, registry)
    context = ToolContext(workspace=str(settings.workspace), session_id=2, actor="test")
    result = await tool.run({"task": "读取 data.txt"}, context)
    assert result.output == "文件内容是 42"


async def test_subagent_iteration_cap(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
) -> None:
    endless = MockLLM(
        [
            MockStep(
                tool_calls=[ToolCall(id="c", name="fs_list", arguments={"path": "."})]
            )
            for _ in range(10)
        ]
    )
    registry = build_default_registry(settings, ask_manager, todo_store)
    tool = SubagentTool(endless, registry, max_iterations=2)
    context = ToolContext(workspace=str(settings.workspace), session_id=3, actor="test")
    result = await tool.run({"task": "无限循环"}, context)
    assert "迭代上限" in result.output
