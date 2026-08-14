"""ACP 最小服务端集成测试（直接驱动分发器，stdio 输出重定向捕获）。"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from pdsh.acp.server import AcpServer, _to_acp_update
from pdsh.config import Settings
from pdsh.core.loop import LoopEvent
from pdsh.llm.mock import MockLLM, MockStep
from pdsh.llm.types import ChatMessage, StreamEvent, ToolSpec


class _BlockingLLM:
    """进入流式后阻塞，直到任务被取消，用于验证 session/cancel 真正打断。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        self.started.set()
        yield StreamEvent(kind="text_delta", delta="部分内容")
        await asyncio.Event().wait()

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> str:
        return ""


@pytest.fixture
def acp_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'acp.db'}",
        llm_provider="mock",
        workspace=tmp_path / "ws",
    )


@pytest.fixture
async def server(acp_settings: Settings) -> AcpServer:
    acp = AcpServer(acp_settings, llm=MockLLM())
    await acp.setup()
    yield acp
    await acp.close()


def _stdout_json(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer)
    return buffer


async def test_initialize_and_session_flow(
    server: AcpServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = _stdout_json(monkeypatch)
    init = await server._dispatch("initialize", {})  # noqa: SLF001
    assert init["agentInfo"]["name"] == "pdsh"

    new_session = await server._dispatch(
        "session/new", {"title": "acp"}
    )  # noqa: SLF001
    session_id = new_session["sessionId"]
    assert session_id.isdigit()

    assert isinstance(server._llm, MockLLM)  # noqa: SLF001
    server._llm.add_step(MockStep(text="ACP 回复"))  # noqa: SLF001
    result = await server._dispatch(  # noqa: SLF001
        "session/prompt",
        {
            "sessionId": session_id,
            "prompt": [{"type": "text", "text": "你好"}],
        },
    )
    assert result == {"stopReason": "end_turn"}

    notifications = [
        json.loads(line) for line in buffer.getvalue().splitlines() if line
    ]
    assert all(n["method"] == "session/update" for n in notifications)
    chunks = [
        n["params"]["update"]
        for n in notifications
        if n["params"]["update"]["sessionUpdate"] == "agent_message_chunk"
    ]
    assert "".join(c["content"]["text"] for c in chunks) == "ACP 回复"


async def test_cancel_and_unknown(
    server: AcpServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stdout_json(monkeypatch)
    assert await server._dispatch("session/cancel", {}) == {  # noqa: SLF001
        "cancelled": False
    }
    with pytest.raises(ValueError):
        await server._dispatch("bogus/method", {})  # noqa: SLF001


async def test_prompt_cancel_interrupts_llm(
    acp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = _stdout_json(monkeypatch)
    blocking = _BlockingLLM()
    acp = AcpServer(acp_settings, llm=blocking)
    await acp.setup()
    try:
        new_session = await acp._dispatch("session/new", {})  # noqa: SLF001
        session_id = new_session["sessionId"]

        acp._start_prompt(  # noqa: SLF001
            1, {"sessionId": session_id, "prompt": [{"type": "text", "text": "hi"}]}
        )
        await asyncio.wait_for(blocking.started.wait(), timeout=1)

        assert await acp._dispatch(  # noqa: SLF001
            "session/cancel", {"sessionId": session_id}
        ) == {"cancelled": True}

        task = acp._prompt_tasks.get(session_id)  # noqa: SLF001
        assert task is not None
        results = await asyncio.gather(task, return_exceptions=True)
        assert results and isinstance(results[0], asyncio.CancelledError)

        lines = [json.loads(line) for line in buffer.getvalue().splitlines() if line]
        responses = [line for line in lines if line.get("id") == 1]
        assert responses and responses[-1]["result"]["stopReason"] == "cancelled"
        assert any(
            line.get("method") == "session/update"
            and line["params"]["update"].get("sessionUpdate") == "agent_cancel"
            for line in lines
        )
    finally:
        await acp.close()


async def test_handle_line_invalid_json(
    server: AcpServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = _stdout_json(monkeypatch)
    await server._handle_line("{not json")  # noqa: SLF001
    error = json.loads(buffer.getvalue().splitlines()[0])
    assert error["error"]["code"] == -32700


async def test_prompt_requires_text_block(
    server: AcpServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stdout_json(monkeypatch)
    new_session = await server._dispatch("session/new", {})  # noqa: SLF001
    with pytest.raises(ValueError):
        await server._dispatch(  # noqa: SLF001
            "session/prompt",
            {"sessionId": new_session["sessionId"], "prompt": []},
        )


def test_update_mapping() -> None:
    text_chunk = _to_acp_update(LoopEvent(kind="text_delta", data={"delta": "x"}))
    assert text_chunk is not None
    assert text_chunk["sessionUpdate"] == "agent_message_chunk"

    tool_call = _to_acp_update(
        LoopEvent(kind="tool_call", data={"call_id": "c", "name": "shell"})
    )
    assert tool_call is not None
    assert tool_call["status"] == "pending"

    tool_result = _to_acp_update(
        LoopEvent(
            kind="tool_result",
            data={"call_id": "c", "output": "ok", "is_error": False},
        )
    )
    assert tool_result is not None
    assert tool_result["status"] == "completed"

    assert _to_acp_update(LoopEvent(kind="done", data={})) is None
