"""MockLLM 与 LLM 类型单元测试。"""

from __future__ import annotations

from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ChatMessage, ToolCall


async def test_scripted_replay() -> None:
    llm = MockLLM(
        [
            MockStep(tool_calls=[ToolCall(id="c1", name="echo", arguments={})]),
            MockStep(text="最终回复"),
        ]
    )
    first = [
        event async for event in llm.stream([ChatMessage(role="user", content="开始")])
    ]
    assert first[0].kind == "tool_calls"
    assert first[0].tool_calls[0].name == "echo"
    assert first[-1].kind == "done"

    second = await llm.complete([ChatMessage(role="user", content="继续")])
    assert second == "最终回复"
    assert len(llm.requests) == 2


async def test_script_exhausted_fallback() -> None:
    llm = MockLLM()
    text = await llm.complete([ChatMessage(role="user", content="hi")])
    assert "脚本已耗尽" in text
