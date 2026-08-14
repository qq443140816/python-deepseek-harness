# Copyright (c) 2026 redfox <591006133@qq.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""会话 CRUD 与工具清单路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from pdsh.api.deps import event_to_out, get_state, session_to_out
from pdsh.api.schemas import (
    EventOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
    ToolInfo,
)
from pdsh.session.store import StaleRevisionError

router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(body: SessionCreate, request: Request) -> SessionOut:
    state = get_state(request)
    entity = await state.store.create_session(body.title)
    return session_to_out(entity)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(request: Request) -> list[SessionOut]:
    state = get_state(request)
    entities = await state.store.list_sessions()
    return [session_to_out(entity) for entity in entities]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: int, request: Request) -> SessionDetail:
    state = get_state(request)
    entity = await state.store.get_session(session_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    event_entities = await state.store.list_event_entities(session_id)
    events: list[EventOut] = [event_to_out(item) for item in event_entities]
    return SessionDetail(session=session_to_out(entity), events=events)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: int, request: Request) -> Response:
    state = get_state(request)
    entity = await state.store.get_session(session_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        await state.store.delete_session(session_id, entity.revision)
    except StaleRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools(request: Request) -> list[ToolInfo]:
    state = get_state(request)
    return [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
        )
        for tool in state.registry.tools()
    ]
