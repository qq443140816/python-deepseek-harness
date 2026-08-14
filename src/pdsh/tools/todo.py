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
