"""AgentLoop contract test（MockLLM 驱动）。

覆盖 DoD 要求的核心行为：多轮对话 → 工具调用 → ask_user 挂起恢复
→ 重复调用护栏 → 迭代上限护栏。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pdsh.config import Settings
from pdsh.core.events import EventType
from pdsh.core.loop import AgentLoop
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ToolCall
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.base import ToolRegistry
from pdsh.tools.todo import TodoStore


@pytest.fixture
def llm() -> MockLLM:
    return MockLLM()


@pytest.fixture
def loop(
    llm: MockLLM,
    registry: ToolRegistry,
    store: SessionStore,
    settings: Settings,
) -> AgentLoop:
    return AgentLoop(
        llm=llm,
        registry=registry,
        store=store,
        max_iterations=settings.max_iterations,
        compaction_threshold=settings.compaction_threshold,
        workspace=str(settings.workspace),
    )


async def _collect(loop: AgentLoop, session_id: int, text: str) -> list[str]:
    return [e.kind async for e in loop.run_turn(session_id, text)]


async def test_plain_answer(loop: AgentLoop, llm: MockLLM, store: SessionStore) -> None:
    llm.add_step(MockStep(text="你好，有什么可以帮你？"))
    session = await store.create_session()
    kinds = await _collect(loop, session.id, "在吗")
    assert kinds == ["text_delta", "done"]
    events = await store.list_events(session.id)
    assert [e.type for e in events] == [EventType.USER, EventType.ASSISTANT]
    assert events[-1].payload["content"] == "你好，有什么可以帮你？"


async def test_tool_call_flow(
    loop: AgentLoop, llm: MockLLM, store: SessionStore, settings: Settings
) -> None:
    llm.add_step(
        MockStep(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="fs_write",
                    arguments={"path": "note.txt", "content": "记录"},
                )
            ]
        )
    )
    llm.add_step(MockStep(text="文件已写入"))
    session = await store.create_session()
    kinds = await _collect(loop, session.id, "帮我写个文件")
    assert kinds == ["tool_call", "tool_result", "text_delta", "done"]
    written = Path(settings.workspace) / "note.txt"
    assert written.read_text(encoding="utf-8") == "记录"
    types = [e.type for e in await store.list_events(session.id)]
    assert types == [
        EventType.USER,
        EventType.TOOL_CALL,
        EventType.TOOL_RESULT,
        EventType.ASSISTANT,
    ]


async def test_unknown_tool_result_fed_back(
    loop: AgentLoop, llm: MockLLM, store: SessionStore
) -> None:
    llm.add_step(MockStep(tool_calls=[ToolCall(id="c1", name="ghost", arguments={})]))
    llm.add_step(MockStep(text="抱歉，该工具不存在"))
    session = await store.create_session()
    kinds = await _collect(loop, session.id, "调用幽灵工具")
    assert "tool_result" in kinds
    events = await store.list_events(session.id)
    tool_result = events[2]
    assert tool_result.payload["is_error"] is True
    assert "未知工具" in tool_result.payload["output"]


async def test_repeat_guard(loop: AgentLoop, llm: MockLLM, store: SessionStore) -> None:
    call = ToolCall(id="c1", name="fs_read", arguments={"path": "x.txt"})
    for _ in range(4):
        llm.add_step(MockStep(tool_calls=[call]))
    llm.add_step(MockStep(text="放弃重试"))
    session = await store.create_session()
    await _collect(loop, session.id, "重复读取")
    events = await store.list_events(session.id)
    results = [e for e in events if e.type is EventType.TOOL_RESULT]
    assert len(results) == 4
    # 前 2 次正常执行（文件不存在错误），第 3 次起被护栏拦截
    assert "重复" not in results[1].payload["output"]
    assert "重复" in results[2].payload["output"]
    assert results[2].payload["is_error"] is True


async def test_max_iterations_guard(
    llm: MockLLM,
    registry: ToolRegistry,
    store: SessionStore,
    settings: Settings,
) -> None:
    busy_loop = AgentLoop(
        llm=llm,
        registry=registry,
        store=store,
        max_iterations=2,
        workspace=str(settings.workspace),
    )
    for _ in range(5):
        llm.add_step(
            MockStep(
                tool_calls=[ToolCall(id="c", name="fs_list", arguments={"path": "."})]
            )
        )
    session = await store.create_session()
    events_out = [e async for e in busy_loop.run_turn(session.id, "死循环")]
    kinds = [e.kind for e in events_out]
    assert "error" in kinds
    assert kinds[-1] == "done"
    error_event = next(e for e in events_out if e.kind == "error")
    assert "最大迭代" in str(error_event.data["message"])


async def test_ask_user_suspend_resume(
    loop: AgentLoop,
    llm: MockLLM,
    store: SessionStore,
    ask_manager: AskUserManager,
) -> None:
    llm.add_step(
        MockStep(
            tool_calls=[
                ToolCall(
                    id="q1", name="ask_user", arguments={"question": "选 A 还是 B？"}
                )
            ]
        )
    )
    llm.add_step(MockStep(text="收到你的选择"))
    session = await store.create_session()

    async def run() -> list[str]:
        return [e.kind async for e in loop.run_turn(session.id, "帮我做决定")]

    task = asyncio.create_task(run())
    for _ in range(300):
        if ask_manager.has_pending(session.id):
            break
        await asyncio.sleep(0.01)
    assert ask_manager.current_question(session.id) == "选 A 还是 B？"
    assert ask_manager.resolve(session.id, "选 A") is True
    kinds = await asyncio.wait_for(task, timeout=5)
    assert kinds == ["tool_call", "ask_user", "tool_result", "text_delta", "done"]
    events = await store.list_events(session.id)
    result = [e for e in events if e.type is EventType.TOOL_RESULT][0]
    assert "选 A" in result.payload["output"]


async def test_todo_tool_via_loop(
    loop: AgentLoop,
    llm: MockLLM,
    store: SessionStore,
    todo_store: TodoStore,
) -> None:
    llm.add_step(
        MockStep(
            tool_calls=[
                ToolCall(
                    id="t1",
                    name="todo_write",
                    arguments={"todos": [{"content": "上线", "status": "pending"}]},
                )
            ]
        )
    )
    llm.add_step(MockStep(text="清单已建立"))
    session = await store.create_session()
    await _collect(loop, session.id, "列个清单")
    assert todo_store.get(session.id)[0]["content"] == "上线"
