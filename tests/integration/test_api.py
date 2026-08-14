"""ASGI 集成测试：会话 CRUD、SSE 对话流、ask_user 恢复。

使用 SQLite 内存库替代 MySQL；LLM 用 MockLLM 脚本回放。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from pdsh.api.app import create_app
from pdsh.api.deps import AppState
from pdsh.config import Settings
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ToolCall


@pytest.fixture
async def env(tmp_path: Path) -> AsyncIterator[SimpleNamespace]:
    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(
        _env_file=None,
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        llm_provider="mock",
        workspace=ws,
    )
    llm = MockLLM()
    app = create_app(settings, llm=llm)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield SimpleNamespace(app=app, llm=llm, client=client, ws=ws)


async def _sse_events(
    client: httpx.AsyncClient, session_id: str, content: str
) -> list[dict[str, object]]:
    async with client.stream(
        "POST",
        f"/api/sessions/{session_id}/messages",
        json={"content": content},
    ) as resp:
        assert resp.status_code == 200
        lines = [line async for line in resp.aiter_lines()]
    return [
        json.loads(line[len("data: ") :]) for line in lines if line.startswith("data: ")
    ]


async def test_healthz(env: SimpleNamespace) -> None:
    resp = await env.client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_session_lifecycle(env: SimpleNamespace) -> None:
    created = await env.client.post("/api/sessions", json={"title": "集成"})
    assert created.status_code == 201
    session_id = created.json()["id"]

    listed = await env.client.get("/api/sessions")
    assert any(s["id"] == session_id for s in listed.json())

    detail = await env.client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["session"]["title"] == "集成"
    assert detail.json()["events"] == []

    deleted = await env.client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 204
    missing = await env.client.get(f"/api/sessions/{session_id}")
    assert missing.status_code == 404
    assert all(
        s["id"] != session_id for s in (await env.client.get("/api/sessions")).json()
    )


async def test_tool_listing(env: SimpleNamespace) -> None:
    resp = await env.client.get("/api/tools")
    names = {t["name"] for t in resp.json()}
    assert {"fs_read", "fs_write", "shell", "ask_user", "todo_write"} <= names


async def test_sse_text_flow(env: SimpleNamespace) -> None:
    env.llm.add_step(MockStep(text="你好！"))
    created = await env.client.post("/api/sessions", json={})
    session_id = created.json()["id"]
    events = await _sse_events(env.client, session_id, "在吗")
    types = [e["type"] for e in events]
    assert types == ["text_delta", "done"]
    assert events[-1]["content"] == "你好！"

    detail = await env.client.get(f"/api/sessions/{session_id}")
    event_types = [e["type"] for e in detail.json()["events"]]
    assert event_types == ["user", "assistant"]


async def test_sse_tool_flow(env: SimpleNamespace) -> None:
    env.llm.add_step(
        MockStep(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="fs_write",
                    arguments={"path": "out.txt", "content": "落地"},
                )
            ]
        )
    )
    env.llm.add_step(MockStep(text="写好了"))
    created = await env.client.post("/api/sessions", json={})
    session_id = created.json()["id"]
    events = await _sse_events(env.client, session_id, "写文件")
    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "text_delta", "done"]
    tool_result = events[1]
    assert tool_result["is_error"] is False
    assert (env.ws / "out.txt").read_text(encoding="utf-8") == "落地"


async def test_sse_ask_user_flow(env: SimpleNamespace) -> None:
    env.llm.add_step(
        MockStep(
            tool_calls=[
                ToolCall(
                    id="q1",
                    name="ask_user",
                    arguments={"question": "今天天气如何？"},
                )
            ]
        )
    )
    env.llm.add_step(MockStep(text="谢谢告知"))
    created = await env.client.post("/api/sessions", json={})
    session_id = created.json()["id"]

    task = asyncio.create_task(_sse_events(env.client, session_id, "问问天气"))
    state: AppState = env.app.state.pdsh
    numeric_id = int(session_id)
    for _ in range(300):
        if state.ask_manager.has_pending(numeric_id):
            break
        await asyncio.sleep(0.01)
    assert state.ask_manager.current_question(numeric_id) == "今天天气如何？"

    resp = await env.client.post(
        f"/api/sessions/{session_id}/responses", json={"answer": "晴天"}
    )
    assert resp.json()["resolved"] is True

    events = await asyncio.wait_for(task, timeout=5)
    types = [e["type"] for e in events]
    assert "ask_user" in types
    assert types[-1] == "done"
    assert events[-1]["content"] == "谢谢告知"

    # 无挂起问题时回复：resolved=False
    idle = await env.client.post(
        f"/api/sessions/{session_id}/responses", json={"answer": "多余"}
    )
    assert idle.json()["resolved"] is False


async def test_message_to_missing_session(env: SimpleNamespace) -> None:
    resp = await env.client.post(
        "/api/sessions/123456/messages", json={"content": "hi"}
    )
    assert resp.status_code == 404


async def test_empty_message_rejected(env: SimpleNamespace) -> None:
    created = await env.client.post("/api/sessions", json={})
    session_id = created.json()["id"]
    resp = await env.client.post(
        f"/api/sessions/{session_id}/messages", json={"content": ""}
    )
    assert resp.status_code == 422
