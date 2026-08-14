"""文件系统工具单元测试（含路径穿越防护）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdsh.tools.base import ToolContext, ToolError
from pdsh.tools.fs import (
    EditFileTool,
    GlobTool,
    GrepTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
    _resolve_safe,
)


@pytest.fixture
def context(workspace: Path) -> ToolContext:
    return ToolContext(workspace=str(workspace), session_id=1)


async def test_write_and_read(context: ToolContext) -> None:
    wrote = await WriteFileTool().run({"path": "sub/a.txt", "content": "你好"}, context)
    assert "已写入" in wrote.output
    read = await ReadFileTool().run({"path": "sub/a.txt"}, context)
    assert read.output == "你好"


async def test_read_missing(context: ToolContext) -> None:
    result = await ReadFileTool().run({"path": "no.txt"}, context)
    assert result.is_error is True


async def test_edit_unique_match(context: ToolContext) -> None:
    await WriteFileTool().run({"path": "b.txt", "content": "foo bar foo"}, context)
    ambiguous = await EditFileTool().run(
        {"path": "b.txt", "old": "foo", "new": "baz"}, context
    )
    assert ambiguous.is_error is True
    exact = await EditFileTool().run(
        {"path": "b.txt", "old": "foo bar foo", "new": "qux"}, context
    )
    assert exact.output == "替换完成"
    read = await ReadFileTool().run({"path": "b.txt"}, context)
    assert read.output == "qux"


async def test_list_and_glob_and_grep(context: ToolContext) -> None:
    await WriteFileTool().run({"path": "d/x.py", "content": "alpha\nbeta"}, context)
    await WriteFileTool().run({"path": "d/y.txt", "content": "gamma"}, context)
    listed = await ListDirTool().run({"path": "d"}, context)
    assert "x.py" in listed.output and "y.txt" in listed.output
    recursive = await ListDirTool().run({"recursive": True}, context)
    assert "x.py" in recursive.output
    globbed = await GlobTool().run({"pattern": "*.py"}, context)
    assert "x.py" in globbed.output
    grep = await GrepTool().run({"pattern": "beta"}, context)
    assert "x.py:2" in grep.output


async def test_list_empty_and_missing(context: ToolContext) -> None:
    empty_dir = Path(context.workspace) / "empty"
    empty_dir.mkdir()
    empty = await ListDirTool().run({"path": "empty"}, context)
    assert "(空目录)" in empty.output
    missing = await ListDirTool().run({"path": "ghost"}, context)
    assert missing.is_error is True


def test_path_traversal_blocked(workspace: Path) -> None:
    with pytest.raises(ToolError):
        _resolve_safe(str(workspace), "../outside.txt")


async def test_traversal_in_tool(context: ToolContext) -> None:
    with pytest.raises(ToolError):
        await ReadFileTool().run({"path": "../secret.txt"}, context)
