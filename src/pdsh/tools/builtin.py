"""默认注册表装配：内置通用工具 + 企业扩展入口。

`extra_tools` 是企业私有工具的挂接点：审批流、知识库检索等
按 Tool 协议实现后传入即可，与内置工具同等参与 agent 循环。
"""

from __future__ import annotations

from collections.abc import Iterable

from pdsh.config import Settings
from pdsh.tools.ask_user import AskUserManager, AskUserTool
from pdsh.tools.base import Tool, ToolRegistry
from pdsh.tools.fs import (
    EditFileTool,
    GlobTool,
    GrepTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from pdsh.tools.shell import ShellTool
from pdsh.tools.todo import TodoStore, TodoWriteTool
from pdsh.tools.web_tools import SearchProvider, WebFetchTool, WebSearchTool


def build_default_registry(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
    *,
    search_provider: SearchProvider | None = None,
    extra_tools: Iterable[Tool] = (),
) -> ToolRegistry:
    """装配默认工具注册表。"""
    registry = ToolRegistry(timeout=settings.tool_timeout)
    builtin: list[Tool] = [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        ListDirTool(),
        GlobTool(),
        GrepTool(),
        ShellTool(),
        WebFetchTool(),
        WebSearchTool(search_provider),
        TodoWriteTool(todo_store),
        AskUserTool(ask_manager, timeout=settings.ask_user_timeout),
    ]
    for tool in builtin:
        registry.register(tool)
    for tool in extra_tools:
        registry.register(tool)
    return registry
