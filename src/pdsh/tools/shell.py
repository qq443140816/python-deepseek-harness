"""shell 命令执行工具。

安全约束：
- 仅允许在 context.workspace 内执行（cwd 固定为工作区）
- 带超时（由注册表统一施加）
- 输出截断，防止超长内容打爆上下文
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pdsh.tools.base import BaseTool, ToolContext, ToolResult

_MAX_OUTPUT_CHARS = 20_000
_DEFAULT_TIMEOUT = 60.0


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + "\n...[输出过长已截断]"


class ShellTool(BaseTool):
    name = "shell"
    description = "在工作区内执行 shell 命令并返回 stdout/stderr"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令"},
            "timeout": {
                "type": "number",
                "description": "超时秒数，默认 60",
                "minimum": 1,
                "maximum": 300,
            },
        },
        "required": ["command"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        workspace = Path(context.workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        timeout = float(arguments.get("timeout", _DEFAULT_TIMEOUT))
        try:
            proc = await asyncio.create_subprocess_shell(  # nosec B602 工作区内受控执行
                arguments["command"],
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return ToolResult(output=f"命令超时（>{timeout}s）", is_error=True)
        except OSError as exc:
            return ToolResult(output=f"命令启动失败: {exc}", is_error=True)
        stdout = stdout_b.decode("utf-8", "replace")
        stderr = stderr_b.decode("utf-8", "replace")
        parts = [
            f"exit_code: {proc.returncode}",
            f"--- stdout ---\n{_truncate(stdout)}",
        ]
        if stderr:
            parts.append(f"--- stderr ---\n{_truncate(stderr)}")
        return ToolResult(
            output="\n".join(parts),
            is_error=proc.returncode != 0,
        )
