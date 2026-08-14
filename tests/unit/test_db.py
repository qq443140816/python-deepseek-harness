"""数据库基类与引擎单元测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

import pdsh.db.base as db_base
from pdsh.config import Settings
from pdsh.db.base import BaseEntity, MinimalEntity, configure_snowflake
from pdsh.db.engine import (
    create_engine_and_sessionmaker,
    init_schema,
    session_scope,
)
from pdsh.db.models import SessionEntity


def test_configure_snowflake() -> None:
    configure_snowflake(7)
    try:
        assert db_base.snowflake.worker_id == 7
    finally:
        configure_snowflake(1)


def test_entity_hierarchy() -> None:
    assert issubclass(BaseEntity, MinimalEntity)
    assert issubclass(SessionEntity, BaseEntity)
    columns = set(SessionEntity.__table__.columns.keys())
    for required in (
        "id",
        "revision",
        "created_by",
        "created_time",
        "updated_by",
        "updated_time",
        "is_deleted",
    ):
        assert required in columns


async def test_session_scope_commit(settings: Settings) -> None:
    engine, maker = create_engine_and_sessionmaker(settings.db_url)
    await init_schema(engine)
    async with session_scope(maker) as session:
        session.add(SessionEntity(title="提交测试"))
    async with maker() as session:
        rows = await session.execute(select(SessionEntity))
        assert len(list(rows.scalars().all())) == 1
    await engine.dispose()


async def test_session_scope_rollback(settings: Settings) -> None:
    engine, maker = create_engine_and_sessionmaker(settings.db_url)
    await init_schema(engine)
    with pytest.raises(RuntimeError):
        async with session_scope(maker) as session:
            session.add(SessionEntity(title="回滚测试"))
            raise RuntimeError("触发回滚")
    async with maker() as session:
        rows = await session.execute(select(SessionEntity))
        assert len(list(rows.scalars().all())) == 0
    await engine.dispose()
