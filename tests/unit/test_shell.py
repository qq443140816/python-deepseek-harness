"""shell 工具单元测试。"""

from __future__ import annotations

from pathlib import Path

from pdsh.tools.base import ToolContext
from pdsh.tools.shell import ShellTool, _truncate


async def test_echo(workspace: Path) -> None:
    context = ToolContext(workspace=str(workspace), session_id=1)
    result = await ShellTool().run({"command": "echo hello-pdsh"}, context)
    assert result.is_error is False
    assert "exit_code: 0" in result.output
    assert "hello-pdsh" in result.output


async def test_nonzero_exit(workspace: Path) -> None:
    context = ToolContext(workspace=str(workspace), session_id=1)
    result = await ShellTool().run(
        {"command": 'python -c "import sys; sys.exit(3)"'}, context
    )
    assert result.is_error is True
    assert "exit_code: 3" in result.output


async def test_workspace_created(workspace: Path) -> None:
    nested = workspace / "not-yet"
    context = ToolContext(workspace=str(nested), session_id=1)
    result = await ShellTool().run({"command": "echo ok"}, context)
    assert result.is_error is False
    assert nested.is_dir()


def test_truncate() -> None:
    long_text = "x" * 30_000
    truncated = _truncate(long_text)
    assert len(truncated) < 30_000
    assert "截断" in truncated
    assert _truncate("short") == "short"
