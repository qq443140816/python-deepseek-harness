"""对话路由：SSE 流式消息 + ask_user 回复。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from pdsh.api.deps import get_state
from pdsh.api.schemas import MessageRequest, RespondRequest, RespondResult

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int, body: MessageRequest, request: Request
) -> StreamingResponse:
    """发送消息并以 SSE 流式返回 agent 事件。

    事件类型：text_delta / thinking_delta / tool_call / tool_result /
    ask_user / done / error。
    """
    state = get_state(request)
    if await state.store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in state.loop.run_turn(session_id, body.content):
                yield _sse({"type": event.kind, **event.data})
        except asyncio.CancelledError:
            # 客户端断开：取消挂起的 ask_user，避免 Future 泄漏
            state.ask_manager.cancel(session_id)
            raise
        except Exception as exc:  # noqa: BLE001 SSE 通道内兜底转错误事件
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/responses", response_model=RespondResult)
async def respond_ask_user(
    session_id: int, body: RespondRequest, request: Request
) -> RespondResult:
    """回复当前会话挂起的 ask_user 问题。"""
    state = get_state(request)
    if await state.store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    resolved = state.ask_manager.resolve(session_id, body.answer)
    return RespondResult(resolved=resolved)
