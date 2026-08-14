"""todo_write 工具：维护会话级任务清单（对齐 dsh todo 包）。"""

from __future__ import annotations

from typing import Any

from pdsh.tools.base import BaseTool, ToolContext, ToolResult

_STATUS = ("pending", "in_progress", "completed")


class TodoStore:
    """会话级待办存储（内存态；持久化落库由仓储层负责）。"""

    def __init__(self) -> None:
        self._items: dict[int, list[dict[str, str]]] = {}

    def get(self, session_id: int) -> list[dict[str, str]]:
        return self._items.setdefault(session_id, [])

    def replace(self, session_id: int, todos: list[dict[str, str]]) -> None:
        self._items[session_id] = todos


class TodoWriteTool(BaseTool):
    name = "todo_write"
    description = "创建或整体更新当前会话的任务清单（全量替换）"
    parameters = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": list(_STATUS),
                        },
                    },
                    "required": ["content", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    def __init__(self, store: TodoStore) -> None:
        self._store = store

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        todos = [
            {"content": t["content"], "status": t["status"]} for t in arguments["todos"]
        ]
        self._store.replace(context.session_id, todos)
        summary = "; ".join(f"[{t['status']}] {t['content']}" for t in todos)
        return ToolResult(output=f"待办已更新（{len(todos)} 项）：{summary}")
