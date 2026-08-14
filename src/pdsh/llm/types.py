"""LLM 领域类型：消息、工具规格、流式事件。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """模型发起的一次工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """对话消息（OpenAI 兼容结构的子集）。"""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class ToolSpec(BaseModel):
    """工具的 JSON Schema 规格，用于随请求下发给模型。"""

    name: str
    description: str
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


class Usage(BaseModel):
    """token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0


class StreamEvent(BaseModel):
    """LLM 流式输出事件。

    kind:
      - text_delta: 正文增量（delta 为增量文本）
      - thinking_delta: 推理过程增量
      - tool_calls: 完整工具调用列表（payload 为 list[ToolCall]）
      - done: 结束（payload 为 Usage）
    """

    kind: Literal["text_delta", "thinking_delta", "tool_calls", "done"]
    delta: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
