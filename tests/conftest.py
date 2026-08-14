"""共享 fixture：内存化的存储、注册表与配置。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pdsh.config import Settings
from pdsh.db.engine import create_engine_and_sessionmaker, init_schema
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.base import ToolRegistry
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def settings(tmp_path: Path, workspace: Path) -> Settings:
    """测试配置：SQLite 文件库 + mock LLM + 超大压缩阈值（避免干扰）。"""
    return Settings(
        _env_file=None,
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        llm_provider="mock",
        workspace=workspace,
        compaction_threshold=1_000_000,
        max_iterations=25,
        tool_timeout=10,
        ask_user_timeout=5,
    )


@pytest.fixture
async def sessionmaker(
    settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine, maker = create_engine_and_sessionmaker(settings.db_url)
    await init_schema(engine)
    yield maker
    await engine.dispose()


@pytest.fixture
async def store(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> SessionStore:
    return SessionStore(sessionmaker)


@pytest.fixture
def ask_manager() -> AskUserManager:
    return AskUserManager()


@pytest.fixture
def todo_store() -> TodoStore:
    return TodoStore()


@pytest.fixture
def registry(
    settings: Settings,
    ask_manager: AskUserManager,
    todo_store: TodoStore,
) -> ToolRegistry:
    return build_default_registry(settings, ask_manager, todo_store)
