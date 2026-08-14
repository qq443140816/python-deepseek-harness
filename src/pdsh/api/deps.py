"""依赖注入：应用状态容器与实体→DTO 转换。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from pdsh.api.schemas import EventOut, SessionOut
from pdsh.config import Settings
from pdsh.core.events import SessionEvent
from pdsh.core.loop import AgentLoop
from pdsh.db.models import SessionEntity, SessionEventEntity
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.base import ToolRegistry
from pdsh.tools.todo import TodoStore


@dataclass
class AppState:
    """应用级共享状态（挂载在 app.state.pdsh）。"""

    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    store: SessionStore
    registry: ToolRegistry
    ask_manager: AskUserManager
    todo_store: TodoStore
    loop: AgentLoop


def get_state(request: Request) -> AppState:
    """从请求中取出应用状态。"""
    state = request.app.state.pdsh
    if not isinstance(state, AppState):
        raise RuntimeError("应用状态未初始化")
    return state


def session_to_out(entity: SessionEntity) -> SessionOut:
    """会话实体 → DTO（ID 转字符串）。"""
    return SessionOut(
        id=str(entity.id),
        title=entity.title,
        revision=entity.revision,
        created_time=entity.created_time,
        updated_time=entity.updated_time,
    )


def event_to_out(entity: SessionEventEntity) -> EventOut:
    """事件实体 → DTO。"""
    event = SessionEvent.load(entity.payload)
    return EventOut(
        id=str(entity.id),
        type=event.type.value,
        payload=event.payload,
        created_time=entity.created_time,
    )
