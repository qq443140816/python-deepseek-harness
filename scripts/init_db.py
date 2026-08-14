"""初始化数据库：确保 MySQL 库存在，并自动创建全部业务表。

用法：

    python scripts/init_db.py

脚本读取项目根目录的 .env（PDSH_DB_URL）。SQLAlchemy 的 create_all 只会
建表、不会建库，因此对 MySQL 会先执行 CREATE DATABASE IF NOT EXISTS；
SQLite 则自动确保父目录存在（:memory: 除外）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from pdsh.config import Settings
from pdsh.db import models  # noqa: F401  导入即注册 metadata
from pdsh.db.base import Base
from pdsh.db.engine import create_engine_and_sessionmaker, init_schema

_MYSQL_CREATE = (
    "CREATE DATABASE IF NOT EXISTS `{db}` "
    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
)


def _ensure_sqlite_parent(database: str) -> None:
    """SQLite 建库前确保数据库文件所在目录存在。"""
    if database in ("", ":memory:"):
        return
    parent = Path(database).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


async def _ensure_mysql_database(url: URL) -> None:
    """连接 MySQL 服务端（不选库）执行 CREATE DATABASE IF NOT EXISTS。"""
    database = url.database or ""
    if not database:
        raise SystemExit("MySQL 连接串缺少数据库名，请检查 PDSH_DB_URL")
    engine = create_async_engine(url.set(database=""))
    try:
        async with engine.begin() as conn:
            await conn.execute(text(_MYSQL_CREATE.format(db=database)))
    finally:
        await engine.dispose()


async def main() -> None:
    settings = Settings()
    url = make_url(settings.db_url)

    backend = url.get_backend_name()
    if backend == "mysql":
        await _ensure_mysql_database(url)
    elif backend == "sqlite":
        _ensure_sqlite_parent(url.database or "")
    else:
        raise SystemExit(f"暂不支持的数据库类型：{backend}")

    engine, _ = create_engine_and_sessionmaker(settings.db_url)
    try:
        await init_schema(engine)
    finally:
        await engine.dispose()

    tables = sorted(Base.metadata.tables)
    print(f"数据库初始化完成：{url.render_as_string(hide_password=True)}")
    print(f"已就绪表（{len(tables)}）：{', '.join(tables)}")


if __name__ == "__main__":
    asyncio.run(main())
