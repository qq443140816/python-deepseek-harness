"""todo_write 工具单元测试。"""

from __future__ import annotations

from pdsh.tools.base import ToolContext
from pdsh.tools.todo import TodoStore, TodoWriteTool


async def test_todo_write_replaces() -> None:
    store = TodoStore()
    tool = TodoWriteTool(store)
    context = ToolContext(workspace=".", session_id=42)
    first = await tool.run(
        {"todos": [{"content": "调研", "status": "completed"}]}, context
    )
    assert "1 项" in first.output
    second = await tool.run(
        {
            "todos": [
                {"content": "开发", "status": "in_progress"},
                {"content": "测试", "status": "pending"},
            ]
        },
        context,
    )
    assert "2 项" in second.output
    current = store.get(42)
    assert [t["content"] for t in current] == ["开发", "测试"]
    assert store.get(999) == []
