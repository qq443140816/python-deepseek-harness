"""子代理委派工具（对齐 dsh subagent）。

在工具内部运行一个独立的简化工具循环：独立上下文、受限工具集
（剔除 ask_user / subagent / todo_write，避免递归与主会话状态污染），
完成后把文本结论回传主循环。
"""

from __future__ import annotations

from typing import Any

from pdsh.llm.base import LLMClient
from pdsh.llm.types import ChatMessage, ToolCall
from pdsh.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult

#: 子代理禁用的工具（防递归、防挂起用户、防主会话状态污染）
_EXCLUDED = frozenset({"ask_user", "subagent", "todo_write"})

_SYSTEM_PROMPT = (
    "你是一个子代理，负责独立完成一个子任务。你可以使用提供的工具收集信息"
    "或执行动作；完成后直接输出简明结论，不要反问。"
)


class SubagentTool(BaseTool):
    """子代理委派：独立上下文 + 受限工具集。"""

    name = "subagent"
    description = "把一个子任务委派给独立子代理完成，返回文本结论"
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "委派给子代理的任务描述",
            },
        },
        "required": ["task"],
    }

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        *,
        max_iterations: int = 8,
    ) -> None:
        self._llm = llm
        self._max_iterations = max_iterations
        self._inner = ToolRegistry(timeout=registry.timeout)
        for tool in registry.tools():
            if tool.name not in _EXCLUDED:
                self._inner.register(tool)

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=arguments["task"]),
        ]
        last_text = ""
        for _ in range(self._max_iterations):
            calls, text = await self._one_step(messages)
            last_text = text or last_text
            if not calls:
                return ToolResult(output=text or "（子代理未产出结论）")
            messages.append(ChatMessage(role="assistant", content="", tool_calls=calls))
            for call in calls:
                result = await self._inner.execute(call.name, call.arguments, context)
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=result.output,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )
        return ToolResult(output=f"子代理达到迭代上限，阶段性进展：{last_text}")

    async def _one_step(
        self, messages: list[ChatMessage]
    ) -> tuple[list[ToolCall], str]:
        calls: list[ToolCall] = []
        text_parts: list[str] = []
        async for event in self._llm.stream(messages, self._inner.specs()):
            if event.kind == "text_delta":
                text_parts.append(event.delta)
            elif event.kind == "tool_calls":
                calls = list(event.tool_calls)
        return calls, "".join(text_parts)
