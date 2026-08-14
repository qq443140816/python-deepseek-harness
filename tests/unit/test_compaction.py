"""上下文压缩单元测试。"""

from __future__ import annotations

from pdsh.compaction import estimate_tokens, maybe_compact, serialize_transcript
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ChatMessage, ToolCall


def test_estimate_tokens_monotonic() -> None:
    short = [ChatMessage(role="user", content="hi")]
    long = [ChatMessage(role="user", content="x" * 3000)]
    assert estimate_tokens(short) < estimate_tokens(long)
    with_tools = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="c", name="shell", arguments={"a": 1})],
        )
    ]
    assert estimate_tokens(with_tools) > 0


def test_serialize_transcript() -> None:
    text = serialize_transcript(
        [
            ChatMessage(role="user", content="问题"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="c", name="fs_read", arguments={})],
            ),
            ChatMessage(role="tool", content="结果", tool_call_id="c", name="fs_read"),
        ]
    )
    assert "[user] 问题" in text
    assert "fs_read" in text


async def test_below_threshold_noop() -> None:
    llm = MockLLM()
    messages = [ChatMessage(role="system", content="s")] + [
        ChatMessage(role="user", content=f"消息{i}") for i in range(4)
    ]
    result, summary = await maybe_compact(llm, messages, threshold=100_000)
    assert result is messages
    assert summary is None
    assert llm.requests == []


async def test_too_few_messages_noop() -> None:
    llm = MockLLM()
    messages = [ChatMessage(role="user", content="x" * 6000)]
    result, summary = await maybe_compact(llm, messages, threshold=100)
    assert result is messages
    assert summary is None


async def test_compaction_summarizes_old_history() -> None:
    llm = MockLLM([MockStep(text="这是摘要")])
    messages = [ChatMessage(role="system", content="sys")] + [
        ChatMessage(role="user", content=f"第{i}轮 " + "y" * 300) for i in range(20)
    ]
    result, summary = await maybe_compact(llm, messages, threshold=100, keep_recent=4)
    assert summary == "这是摘要"
    assert result[0].role == "system"
    assert "[以下是更早对话历史的摘要]" in result[1].content
    # 系统消息 + 摘要消息 + 最近 4 条
    assert len(result) == 6
    assert result[-1].content.startswith("第19轮")
    # 摘要请求包含旧历史转录
    assert len(llm.requests) == 1
    assert "第0轮" in llm.requests[0][-1].content
