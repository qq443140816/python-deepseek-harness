"""会话仓储单元测试：CRUD、乐观锁、软删除。"""

from __future__ import annotations

import pytest

from pdsh.core.events import EventType
from pdsh.session.store import SessionStore, StaleRevisionError


async def test_create_get_list(store: SessionStore) -> None:
    entity = await store.create_session("第一个会话")
    assert entity.id > 0
    assert entity.revision == 0

    fetched = await store.get_session(entity.id)
    assert fetched is not None
    assert fetched.title == "第一个会话"

    await store.create_session("第二个会话")
    sessions = await store.list_sessions()
    assert [s.title for s in sessions] == ["第二个会话", "第一个会话"]


async def test_get_missing(store: SessionStore) -> None:
    assert await store.get_session(999_999) is None


async def test_update_title_with_optimistic_lock(store: SessionStore) -> None:
    entity = await store.create_session("旧标题")
    await store.update_title(entity.id, "新标题", revision=0)
    updated = await store.get_session(entity.id)
    assert updated is not None
    assert updated.title == "新标题"
    assert updated.revision == 1
    with pytest.raises(StaleRevisionError):
        await store.update_title(entity.id, "冲突", revision=0)


async def test_soft_delete(store: SessionStore) -> None:
    entity = await store.create_session("待删除")
    await store.delete_session(entity.id, revision=0)
    assert await store.get_session(entity.id) is None
    assert all(s.id != entity.id for s in await store.list_sessions())
    with pytest.raises(StaleRevisionError):
        await store.delete_session(entity.id, revision=0)


async def test_events_append_and_list(store: SessionStore) -> None:
    entity = await store.create_session()
    await store.append_event(
        entity.id, EventType.USER, {"content": "你好"}, actor="user"
    )
    await store.append_event(entity.id, EventType.ASSISTANT, {"content": "您好"})
    events = await store.list_events(entity.id)
    assert [e.type for e in events] == [EventType.USER, EventType.ASSISTANT]
    assert events[0].payload == {"content": "你好"}

    entities = await store.list_event_entities(entity.id)
    assert entities[0].created_by == "user"
    assert entities[1].created_by == "system"
    # 其他会话不可见
    other = await store.create_session()
    assert await store.list_events(other.id) == []
