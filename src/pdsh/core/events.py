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

"""会话事件模型：「模型可见 ⟺ 已记录」。

所有模型可见内容（用户消息、助手回复、工具调用与结果、压缩摘要）
都以事件行落库；重放会话即重读事件流并组装为 ChatMessage。
THINKING / SYSTEM_NOTE 仅供前端展示与审计，不进入模型上下文。
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pdsh.llm.types import ChatMessage, ToolCall


class EventType(str, Enum):
    """会话事件类型。"""

    USER = "user"
    ASSISTANT = "assistant"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    COMPACTION = "compaction"
    SYSTEM_NOTE = "system_note"


#: 重放时进入模型上下文的事件类型
_VISIBLE: frozenset[EventType] = frozenset(
    {
        EventType.USER,
        EventType.ASSISTANT,
        EventType.TOOL_CALL,
        EventType.TOOL_RESULT,
        EventType.COMPACTION,
    }
)


class SessionEvent(BaseModel):
    """领域层会话事件（与存储行一一对应）。"""

    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)

    def dump(self) -> str:
        """序列化为落库 JSON 文本。"""
        return json.dumps(
            {"type": self.type.value, "payload": self.payload},
            ensure_ascii=False,
        )

    @classmethod
    def load(cls, raw: str) -> "SessionEvent":
        """从落库 JSON 文本反序列化。"""
        data = json.loads(raw)
        return cls(type=EventType(data["type"]), payload=data.get("payload", {}))


def replay_messages(events: list[SessionEvent]) -> list[ChatMessage]:
    """把事件流组装为模型可见消息列表。

    COMPACTION 事件会丢弃其之前的全部可见历史，替换为一条摘要消息。
    """
    messages: list[ChatMessage] = []
    for event in events:
        if event.type not in _VISIBLE:
            continue
        if event.type is EventType.COMPACTION:
            summary = event.payload.get("summary", "")
            messages = [
                ChatMessage(
                    role="user",
                    content=f"[以下是更早对话历史的摘要]\n{summary}",
                )
            ]
            continue
        message = _to_message(event)
        if message is not None:
            messages.append(message)
    return messages


def _to_message(event: SessionEvent) -> ChatMessage | None:
    payload = event.payload
    if event.type is EventType.USER:
        return ChatMessage(role="user", content=payload.get("content", ""))
    if event.type is EventType.ASSISTANT:
        return ChatMessage(role="assistant", content=payload.get("content", ""))
    if event.type is EventType.TOOL_CALL:
        calls = [
            ToolCall(
                id=item["id"],
                name=item["name"],
                arguments=item.get("arguments", {}),
            )
            for item in payload.get("calls", [])
        ]
        return ChatMessage(role="assistant", content="", tool_calls=calls)
    if event.type is EventType.TOOL_RESULT:
        return ChatMessage(
            role="tool",
            content=payload.get("output", ""),
            tool_call_id=payload.get("call_id", ""),
            name=payload.get("name", ""),
        )
    return None
