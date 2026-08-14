"""LLM 客户端协议定义。"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from pdsh.llm.types import ChatMessage, StreamEvent, ToolSpec


@runtime_checkable
class LLMClient(Protocol):
    """模型客户端协议：流式对话 + 一次性补全。"""

    def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式对话，产出 StreamEvent 序列，以 done 事件收尾。

        实现方以异步生成器提供；调用方直接 `async for` 消费。
        """
        ...

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> str:
        """一次性补全，返回最终正文文本（内部聚合流式输出）。"""
        ...
