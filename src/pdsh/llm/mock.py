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

"""MockLLM：脚本化回放的模型客户端，用于 contract test 与无 key 开发。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pdsh.llm.types import ChatMessage, StreamEvent, ToolCall, ToolSpec, Usage


class MockStep:
    """一步脚本：要么回复文本，要么发起工具调用。"""

    def __init__(
        self,
        text: str = "",
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self.text = text
        self.tool_calls = tool_calls or []


class MockLLM:
    """按预设脚本逐步回放的 LLM 客户端。

    每次 stream() 调用消费脚本中的一步；脚本耗尽后回退为纯文本
    "[mock] 脚本已耗尽"，保证测试可预期。
    """

    def __init__(self, steps: list[MockStep] | None = None) -> None:
        self._steps = list(steps or [])
        self._cursor = 0
        self.requests: list[list[ChatMessage]] = []

    def add_step(self, step: MockStep) -> None:
        self._steps.append(step)

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        self.requests.append(list(messages))
        if self._cursor < len(self._steps):
            step = self._steps[self._cursor]
            self._cursor += 1
        else:
            step = MockStep(text="[mock] 脚本已耗尽")
        if step.tool_calls:
            yield StreamEvent(kind="tool_calls", tool_calls=step.tool_calls)
        elif step.text:
            yield StreamEvent(kind="text_delta", delta=step.text)
        yield StreamEvent(kind="done", usage=Usage())

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> str:
        parts: list[str] = []
        async for event in self.stream(messages, tools):
            if event.kind == "text_delta":
                parts.append(event.delta)
        return "".join(parts)
