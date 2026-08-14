# Copyright (c) 2026 redfox <591006133@qq.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
