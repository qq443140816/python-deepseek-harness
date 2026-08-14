"""ask_user 工具与管理器单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from pdsh.tools.ask_user import AskUserManager, AskUserTool
from pdsh.tools.base import ToolContext


async def test_register_and_resolve() -> None:
    manager = AskUserManager()
    future = manager.register(1, "选哪个？")
    assert manager.has_pending(1)
    assert manager.current_question(1) == "选哪个？"
    assert manager.resolve(1, "方案 A") is True
    assert await future == "方案 A"
    assert manager.has_pending(1) is False


def test_resolve_without_pending() -> None:
    manager = AskUserManager()
    assert manager.resolve(123, "x") is False
    assert manager.current_question(123) is None


async def test_cancel() -> None:
    manager = AskUserManager()
    future = manager.register(2, "问题")
    manager.cancel(2)
    assert future.cancelled()
    assert manager.has_pending(2) is False
    manager.cancel(2)  # 重复取消不报错


async def test_tool_waits_for_answer() -> None:
    manager = AskUserManager()
    tool = AskUserTool(manager, timeout=5)
    context = ToolContext(workspace=".", session_id=7)

    async def answer_later() -> None:
        for _ in range(200):
            if manager.has_pending(7):
                manager.resolve(7, "42")
                return
            await asyncio.sleep(0.01)

    result, _ = await asyncio.gather(
        tool.run({"question": "生命宇宙的终极答案？"}, context), answer_later()
    )
    assert result.is_error is False
    assert "42" in result.output


async def test_tool_timeout() -> None:
    manager = AskUserManager()
    tool = AskUserTool(manager, timeout=0.05)
    context = ToolContext(workspace=".", session_id=8)
    result = await tool.run({"question": "无人应答"}, context)
    assert result.is_error is True
    assert "超时" in result.output
    assert manager.has_pending(8) is False


async def test_reject_second_question_while_pending() -> None:
    manager = AskUserManager()
    tool = AskUserTool(manager, timeout=5)
    context = ToolContext(workspace=".", session_id=9)
    task = asyncio.create_task(tool.run({"question": "第一问"}, context))
    for _ in range(200):
        if manager.has_pending(9):
            break
        await asyncio.sleep(0.01)
    second = await tool.run({"question": "第二问"}, context)
    assert second.is_error is True
    manager.resolve(9, "收尾")
    await task


@pytest.mark.parametrize("session_id", [1, 2])
def test_manager_isolation(session_id: int) -> None:
    manager = AskUserManager()
    assert manager.has_pending(session_id) is False
