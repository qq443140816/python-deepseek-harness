"""生成 eval-report.json：golden dataset 跑 3 轮取中位数（AGENTS.md 4.2）。

MockLLM 下评估是确定性的；脚本保持与真实 LLM 评估一致的流程形态。
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

from pdsh.config import Settings
from pdsh.core.events import EventType
from pdsh.core.loop import AgentLoop
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ToolCall
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore

SCENARIOS = [
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
                        arguments={
                            "todos": [{"content": "评估", "status": "pending"}]
                        },
                    )
                ]
            ),
            MockStep(text="清单已建立，评估待办一项。"),
        ],
        "expect_final": "清单已建立，评估待办一项。",
    },
]


async def run_round(settings: Settings) -> dict[str, float]:
    engine_dir = Path(settings.db_url.split("///")[-1]).parent
    engine_dir.mkdir(parents=True, exist_ok=True)
    from pdsh.db.engine import create_engine_and_sessionmaker, init_schema

    engine, maker = create_engine_and_sessionmaker(settings.db_url)
    await init_schema(engine)
    store = SessionStore(maker)
    registry = build_default_registry(settings, AskUserManager(), TodoStore())

    passed = 0
    latencies: list[float] = []
    for scenario in SCENARIOS:
        llm = MockLLM([MockStep(**_step_kwargs(s)) for s in scenario["steps"]])
        loop = AgentLoop(
            llm=llm,
            registry=registry,
            store=store,
            workspace=str(settings.workspace),
        )
        session = await store.create_session(scenario["id"])
        start = time.perf_counter()
        async for _ in loop.run_turn(session.id, scenario["input"]):
            pass
        latencies.append(time.perf_counter() - start)
        events = await store.list_events(session.id)
        assistant = [e for e in events if e.type is EventType.ASSISTANT]
        if assistant and assistant[-1].payload["content"] == scenario["expect_final"]:
            passed += 1
    await engine.dispose()
    return {
        "completion_rate": passed / len(SCENARIOS),
        "p95_latency_s": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
    }


def _step_kwargs(step: MockStep) -> dict[str, object]:
    return {"text": step.text, "tool_calls": step.tool_calls}


async def main() -> None:
    tmp = Path(__file__).resolve().parents[1] / "eval_workdir"
    rounds = []
    for i in range(3):
        settings = Settings(
            _env_file=None,
            db_url=f"sqlite+aiosqlite:///{tmp / f'eval_{i}.db'}",
            llm_provider="mock",
            workspace=tmp / "ws",
        )
        rounds.append(await run_round(settings))
    report = {
        "generated_by": "scripts/gen_eval_report.py",
        "llm_provider": "mock（确定性回放）",
        "rounds": rounds,
        "median": {
            "completion_rate": statistics.median(
                r["completion_rate"] for r in rounds
            ),
            "p95_latency_s": statistics.median(
                r["p95_latency_s"] for r in rounds
            ),
        },
        "thresholds": {
            "completion_rate": 0.95,
            "p95_latency_s": 3.0,
        },
    }
    out = Path(__file__).resolve().parents[1] / "eval-report.json"
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["median"], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
