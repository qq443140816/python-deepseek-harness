"""实体基类体系。

- MinimalEntity：最小实体基类，仅提供雪花主键。
- BaseEntity：通用实体基类，所有业务表必须继承。
  提供 revision 乐观锁、created_by/created_time/updated_by/updated_time
  审计字段与 is_deleted 软删除标记。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pdsh.ids import SnowflakeGenerator

#: 全局雪花生成器（worker_id 由应用启动时按配置重建）
snowflake = SnowflakeGenerator(worker_id=1)


def configure_snowflake(worker_id: int) -> None:
    """按配置重置全局雪花生成器。"""
    global snowflake
    snowflake = SnowflakeGenerator(worker_id=worker_id)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""


class MinimalEntity(Base):
    """最小实体基类：仅雪花主键（BIGINT）。"""

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=lambda: snowflake.next_id(),
        comment="雪花主键",
    )


class BaseEntity(MinimalEntity):
    """通用实体基类：乐观锁 + 审计 + 软删除。"""

    __abstract__ = True
    __mapper_args__ = {"eager_defaults": True}

    revision: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="乐观锁版本号"
    )
    created_by: Mapped[str] = mapped_column(
        String(64), default="system", nullable=False, comment="创建人"
    )
    created_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_by: Mapped[str] = mapped_column(
        String(64), default="system", nullable=False, comment="更新人"
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
    is_deleted: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="软删除：0 正常 1 删除"
    )
