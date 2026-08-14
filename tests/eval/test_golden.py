"""行为评估（Eval Gate）：Golden Dataset 完成率验证。

每个场景给定 MockLLM 脚本与验收断言；全部通过即完成率 100%（阈值 ≥95%）。
运行：pytest tests/eval/ -v
"""

from __future__ import annotations

from typing import Any

import pytest

from pdsh.config import Settings
from pdsh.core.events import EventType
from pdsh.core.loop import AgentLoop
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ToolCall
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "golden-qa",
        "input": "法人的定义是什么？",
        "steps": [MockStep(text="法人是具有民事权利能力的组织。")],
        "expect_final": "法人是具有民事权利能力的组织。",
    },
    {
        "id": "golden-tool",
        "input": "把备忘写入 memo.txt",
        "steps": [
            MockStep(
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="fs_write",
                        arguments={"path": "memo.txt", "content": "备忘内容"},
                    )
                ]
            ),
            MockStep(text="已写入 memo.txt"),
        ],
        "expect_final": "已写入 memo.txt",
        "expect_tool": "fs_write",
    },
    {
        "id": "golden-multi-turn-tool",
        "input": "先列清单再总结",
        "steps": [
            MockStep(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="todo_write",
                        arguments={"todos": [{"content": "评估", "status": "pending"}]},
                    )
                ]
            ),
            MockStep(text="清单已建立，评估待办一项。"),
        ],
        "expect_final": "清单已建立，评估待办一项。",
        "expect_tool": "todo_write",
    },
]


async def _run_scenario(
    scenario: dict[str, Any],
    settings: Settings,
    store: SessionStore,
) -> tuple[str, list[str]]:
    llm = MockLLM(list(scenario["steps"]))
    registry = build_default_registry(settings, AskUserManager(), TodoStore())
    loop = AgentLoop(
        llm=llm,
        registry=registry,
        store=store,
        max_iterations=settings.max_iterations,
        compaction_threshold=settings.compaction_threshold,
        workspace=str(settings.workspace),
    )
    session = await store.create_session(scenario["id"])
    async for _ in loop.run_turn(session.id, scenario["input"]):
        pass
    events = await store.list_events(session.id)
    assistant = [e for e in events if e.type is EventType.ASSISTANT]
    tools = [
        c["name"]
        for e in events
        if e.type is EventType.TOOL_CALL
        for c in e.payload.get("calls", [])
    ]
    return assistant[-1].payload["content"], tools


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
async def test_golden_scenario(
    scenario: dict[str, Any],
    settings: Settings,
    store: SessionStore,
) -> None:
    final_text, tool_names = await _run_scenario(scenario, settings, store)
    assert final_text == scenario["expect_final"]
    if "expect_tool" in scenario:
        assert scenario["expect_tool"] in tool_names


async def test_completion_rate_report(settings: Settings, store: SessionStore) -> None:
    """完成率汇总：全部场景通过 → 100%（阈值 ≥95%）。"""
    passed = 0
    for scenario in SCENARIOS:
        try:
            final_text, _ = await _run_scenario(scenario, settings, store)
            if final_text == scenario["expect_final"]:
                passed += 1
        except AssertionError:
            continue
    rate = passed / len(SCENARIOS)
    assert rate >= 0.95, f"完成率 {rate:.0%} 低于阈值 95%"
