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

"""Agent 主循环（对齐 dsh agent-loop）。

流程：用户消息落库 → 组装上下文（含压缩）→ LLM 流式调用
→ 有工具调用则逐个执行并回填 → 直至产出最终回复或触发护栏。

护栏：max_iterations 迭代上限、同参数重复调用拦截、单工具超时
（注册表施加）、ask_user 挂起/恢复。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pdsh.compaction import maybe_compact
from pdsh.core.events import EventType, replay_messages
from pdsh.core.prompt import build_system_prompt
from pdsh.llm.base import LLMClient
from pdsh.llm.types import ChatMessage, ToolCall, Usage
from pdsh.tools.base import ToolContext, ToolRegistry

if TYPE_CHECKING:
    from pdsh.session.store import SessionStore

#: 同一 turn 内，同参数的相同工具调用最多执行次数
_MAX_REPEAT = 2

LoopEventKind = Literal[
    "text_delta",
    "thinking_delta",
    "tool_call",
    "tool_result",
    "ask_user",
    "done",
    "error",
]


@dataclass
class LoopEvent:
    """AgentLoop 产出、供 SSE 推送的事件。"""

    kind: LoopEventKind
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """一次 turn 的结果摘要。"""

    final_text: str = ""
    iterations: int = 0
    usage: Usage = field(default_factory=Usage)


@dataclass
class _StepAcc:
    """单次 LLM 调用的聚合器。"""

    text: str = ""
    thinking: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class AgentLoop:
    """Agent 主循环；实例无 turn 级状态，可复用。"""

    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        store: SessionStore,
        max_iterations: int = 25,
        compaction_threshold: int = 8000,
        workspace: str = "workspace",
        actor: str = "agent",
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._store = store
        self._max_iterations = max_iterations
        self._compaction_threshold = compaction_threshold
        self._workspace = workspace
        self._actor = actor

    async def run_turn(
        self, session_id: int, user_input: str
    ) -> AsyncIterator[LoopEvent]:
        """执行一次完整 turn，流式产出 LoopEvent。"""
        await self._store.append_event(
            session_id, EventType.USER, {"content": user_input}, actor="user"
        )
        repeat_counts: dict[str, int] = {}
        result = TurnResult()
        for iteration in range(1, self._max_iterations + 1):
            result.iterations = iteration
            messages = await self._compose_messages(session_id)
            acc = _StepAcc()
            async for event in self._stream_llm(messages, acc):
                yield event
            result.final_text = acc.text
            result.usage = acc.usage
            if acc.thinking:
                await self._store.append_event(
                    session_id,
                    EventType.THINKING,
                    {"content": acc.thinking},
                )
            if not acc.calls:
                await self._store.append_event(
                    session_id,
                    EventType.ASSISTANT,
                    {"content": acc.text},
                    actor=self._actor,
                )
                yield LoopEvent(kind="done", data={"content": acc.text})
                return
            await self._store.append_event(
                session_id,
                EventType.TOOL_CALL,
                {"calls": [_call_to_dict(c) for c in acc.calls]},
                actor=self._actor,
            )
            for call in acc.calls:
                async for event in self._run_one_tool(session_id, call, repeat_counts):
                    yield event
        note = f"达到最大迭代次数 {self._max_iterations}，已终止本轮"
        await self._store.append_event(
            session_id, EventType.SYSTEM_NOTE, {"content": note}
        )
        yield LoopEvent(kind="error", data={"message": note})
        yield LoopEvent(kind="done", data={"content": result.final_text})

    async def _stream_llm(
        self, messages: list[ChatMessage], acc: _StepAcc
    ) -> AsyncIterator[LoopEvent]:
        async for event in self._llm.stream(messages, self._registry.specs()):
            if event.kind == "text_delta":
                acc.text += event.delta
                yield LoopEvent(kind="text_delta", data={"delta": event.delta})
            elif event.kind == "thinking_delta":
                acc.thinking += event.delta
                yield LoopEvent(kind="thinking_delta", data={"delta": event.delta})
            elif event.kind == "tool_calls":
                acc.calls = list(event.tool_calls)
            elif event.kind == "done":
                acc.usage = event.usage

    async def _compose_messages(self, session_id: int) -> list[ChatMessage]:
        events = await self._store.list_events(session_id)
        system = build_system_prompt(tool_names=self._registry.names())
        messages = [ChatMessage(role="system", content=system)]
        messages.extend(replay_messages(events))
        compacted, summary = await maybe_compact(
            self._llm, messages, threshold=self._compaction_threshold
        )
        if summary is not None:
            await self._store.append_event(
                session_id, EventType.COMPACTION, {"summary": summary}
            )
        return compacted

    async def _run_one_tool(
        self,
        session_id: int,
        call: ToolCall,
        repeat_counts: dict[str, int],
    ) -> AsyncIterator[LoopEvent]:
        arguments = call.arguments
        yield LoopEvent(
            kind="tool_call",
            data={"call_id": call.id, "name": call.name, "arguments": arguments},
        )
        if call.name == "ask_user":
            yield LoopEvent(
                kind="ask_user",
                data={
                    "call_id": call.id,
                    "question": str(arguments.get("question", "")),
                },
            )
        signature = json.dumps(
            [call.name, arguments], sort_keys=True, ensure_ascii=False
        )
        repeat_counts[signature] = repeat_counts.get(signature, 0) + 1
        if repeat_counts[signature] > _MAX_REPEAT:
            output = (
                f"检测到工具 {call.name} 以相同参数重复调用"
                f"（超过 {_MAX_REPEAT} 次），已拒绝执行。"
                "请更换思路或直接回复用户。"
            )
            is_error = True
        else:
            context = ToolContext(
                workspace=self._workspace,
                session_id=session_id,
                actor=self._actor,
            )
            executed = await self._registry.execute(call.name, arguments, context)
            output, is_error = executed.output, executed.is_error
        await self._store.append_event(
            session_id,
            EventType.TOOL_RESULT,
            {
                "call_id": call.id,
                "name": call.name,
                "output": output,
                "is_error": is_error,
            },
            actor=self._actor,
        )
        yield LoopEvent(
            kind="tool_result",
            data={
                "call_id": call.id,
                "name": call.name,
                "output": output,
                "is_error": is_error,
            },
        )


def _call_to_dict(call: ToolCall) -> dict[str, Any]:
    return {"id": call.id, "name": call.name, "arguments": call.arguments}
