"""ask_user 工具：向用户提问并挂起等待回复（对齐 dsh interaction）。

机制：工具执行时创建 Future 并挂起；API 层收到用户回复后 resolve，
工具继续返回答案给模型。超时返回错误结果，不中断会话。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pdsh.tools.base import BaseTool, ToolContext, ToolResult


@dataclass
class PendingQuestion:
    """一次挂起的提问。"""

    question: str
    future: asyncio.Future[str]
    session_id: int


@dataclass
class AskUserManager:
    """管理挂起的 ask_user 提问。"""

    _pending: dict[int, PendingQuestion] = field(default_factory=dict)

    def has_pending(self, session_id: int) -> bool:
        return session_id in self._pending

    def current_question(self, session_id: int) -> str | None:
        item = self._pending.get(session_id)
        return item.question if item else None

    def register(self, session_id: int, question: str) -> asyncio.Future[str]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending[session_id] = PendingQuestion(
            question=question, future=future, session_id=session_id
        )
        return future

    def resolve(self, session_id: int, answer: str) -> bool:
        """用户回复后唤醒等待中的工具；无挂起提问返回 False。"""
        item = self._pending.pop(session_id, None)
        if item is None or item.future.done():
            return False
        item.future.set_result(answer)
        return True

    def cancel(self, session_id: int) -> None:
        item = self._pending.pop(session_id, None)
        if item is not None and not item.future.done():
            item.future.cancel()


class AskUserTool(BaseTool):
    name = "ask_user"
    description = "向用户提出一个需要人工回答的问题，并等待回复后继续"
    parameters = {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    }

    def __init__(self, manager: AskUserManager, timeout: float = 600.0) -> None:
        self._manager = manager
        self._timeout = timeout

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        if self._manager.has_pending(context.session_id):
            return ToolResult(
                output="当前会话已有未回答的问题，请等待用户回复", is_error=True
            )
        future = self._manager.register(context.session_id, arguments["question"])
        try:
            answer = await asyncio.wait_for(future, timeout=self._timeout)
        except asyncio.TimeoutError:
            self._manager.cancel(context.session_id)
            return ToolResult(
                output=f"等待用户回复超时（>{self._timeout}s）", is_error=True
            )
        return ToolResult(output=f"用户回复：{answer}")
