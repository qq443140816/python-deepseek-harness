"""上下文压缩（对齐 dsh compaction 包）。

当上下文 token 估算超过阈值时，把较早的历史消息摘要为一条压缩消息，
保留最近若干轮原文。摘要由 LLM 生成；压缩结果由调用方以 COMPACTION
事件落库，重放时自动截断旧历史。
"""

from __future__ import annotations

from pdsh.llm.base import LLMClient
from pdsh.llm.types import ChatMessage

_COMPACT_INSTRUCTION = (
    "请把下面的对话历史压缩为一段简明摘要，保留：用户目标、已达成的关键结论、"
    "重要的工具调用结果、尚未完成的事项。不要添加历史中没有的信息。"
)


def estimate_tokens(messages: list[ChatMessage]) -> int:
    """粗粒度 token 估算：总字符数 / 3（中英文混合场景的经验近似）。"""
    chars = 0
    for message in messages:
        chars += len(message.content)
        for call in message.tool_calls:
            chars += len(call.name) + len(str(call.arguments))
    return chars // 3


def serialize_transcript(messages: list[ChatMessage]) -> str:
    """把消息列表序列化为可读文本，供摘要使用。"""
    lines: list[str] = []
    for message in messages:
        if message.role == "tool":
            lines.append(f"[工具结果 {message.name}] {message.content}")
        elif message.tool_calls:
            names = ", ".join(c.name for c in message.tool_calls)
            lines.append(f"[助手调用工具 {names}]")
        else:
            lines.append(f"[{message.role}] {message.content}")
    return "\n".join(lines)


async def maybe_compact(
    llm: LLMClient,
    messages: list[ChatMessage],
    *,
    threshold: int,
    keep_recent: int = 6,
) -> tuple[list[ChatMessage], str | None]:
    """超过阈值则压缩历史。

    返回 (新消息列表, 摘要文本或 None)。消息数不足以拆分时原样返回。
    """
    if estimate_tokens(messages) < threshold:
        return messages, None
    head, body = _split_system(messages)
    if len(body) <= keep_recent:
        return messages, None
    old, recent = body[:-keep_recent], body[-keep_recent:]
    transcript = serialize_transcript(old)
    summary = await llm.complete(
        [
            ChatMessage(role="system", content=_COMPACT_INSTRUCTION),
            ChatMessage(role="user", content=transcript),
        ]
    )
    summary = summary.strip() or "（历史摘要为空）"
    compacted = [
        ChatMessage(role="user", content=f"[以下是更早对话历史的摘要]\n{summary}")
    ]
    return head + compacted + recent, summary


def _split_system(
    messages: list[ChatMessage],
) -> tuple[list[ChatMessage], list[ChatMessage]]:
    if messages and messages[0].role == "system":
        return messages[:1], messages[1:]
    return [], messages
