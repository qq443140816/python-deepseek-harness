"""会话仓储：会话与事件的 CRUD。

- 更新类操作一律走 revision 乐观锁校验；
- 事件追加为插入行，无并发冲突；
- 「模型可见 ⟺ 已记录」：事件行是模型上下文的唯一事实来源。
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pdsh.core.events import EventType, SessionEvent
from pdsh.db.models import SessionEntity, SessionEventEntity


class StaleRevisionError(RuntimeError):
    """乐观锁冲突：提交的 revision 与库中不一致。"""


class SessionStore:
    """会话/事件仓储（绑定一个 async_sessionmaker）。"""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        actor: str = "system",
    ) -> None:
        self._sessionmaker = sessionmaker
        self._actor = actor

    async def create_session(self, title: str = "") -> SessionEntity:
        async with self._sessionmaker() as session:
            entity = SessionEntity(
                title=title, created_by=self._actor, updated_by=self._actor
            )
            session.add(entity)
            await session.commit()
            return entity

    async def list_sessions(self) -> list[SessionEntity]:
        async with self._sessionmaker() as session:
            rows = await session.execute(
                select(SessionEntity)
                .where(SessionEntity.is_deleted == 0)
                .order_by(SessionEntity.id.desc())
            )
            return list(rows.scalars().all())

    async def get_session(self, session_id: int) -> SessionEntity | None:
        async with self._sessionmaker() as session:
            entity = await session.get(SessionEntity, session_id)
            if entity is None or entity.is_deleted != 0:
                return None
            return entity

    async def update_title(self, session_id: int, title: str, revision: int) -> None:
        await self._guarded_update(
            session_id, revision, {"title": title, "updated_by": self._actor}
        )

    async def delete_session(self, session_id: int, revision: int) -> None:
        """软删除（is_deleted=1）+ revision 递增。"""
        await self._guarded_update(
            session_id,
            revision,
            {"is_deleted": 1, "updated_by": self._actor},
        )

    async def _guarded_update(
        self, session_id: int, revision: int, values: dict[str, Any]
    ) -> None:
        async with self._sessionmaker() as session:
            result = await session.execute(
                update(SessionEntity)
                .where(
                    SessionEntity.id == session_id,
                    SessionEntity.revision == revision,
                    SessionEntity.is_deleted == 0,
                )
                .values(revision=revision + 1, **values)
            )
            await session.commit()
            rowcount = cast("CursorResult[Any]", result).rowcount
            if rowcount == 0:
                raise StaleRevisionError(
                    f"会话 {session_id} 更新失败：revision {revision} 已过期"
                )

    async def append_event(
        self,
        session_id: int,
        event_type: EventType,
        payload: dict[str, Any],
        actor: str | None = None,
    ) -> SessionEventEntity:
        event = SessionEvent(type=event_type, payload=payload)
        async with self._sessionmaker() as session:
            entity = SessionEventEntity(
                session_id=session_id,
                event_type=event_type.value,
                payload=event.dump(),
                created_by=actor or self._actor,
                updated_by=actor or self._actor,
            )
            session.add(entity)
            await session.commit()
            return entity

    async def list_events(self, session_id: int) -> list[SessionEvent]:
        entities = await self.list_event_entities(session_id)
        return [SessionEvent.load(row.payload) for row in entities]

    async def list_event_entities(self, session_id: int) -> list[SessionEventEntity]:
        """原始事件行（含 ID/时间戳，供 API 详情展示）。"""
        async with self._sessionmaker() as session:
            rows = await session.execute(
                select(SessionEventEntity)
                .where(
                    SessionEventEntity.session_id == session_id,
                    SessionEventEntity.is_deleted == 0,
                )
                .order_by(SessionEventEntity.id.asc())
            )
            return list(rows.scalars().all())
