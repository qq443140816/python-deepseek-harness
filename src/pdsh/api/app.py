"""FastAPI 应用工厂 + 前端静态托管。

生产入口：`uvicorn pdsh.api.app:app`（模块级 app 由默认配置构建）。
测试可调用 create_app() 注入 Settings / MockLLM / 内存库。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from pdsh import __version__
from pdsh.api.deps import AppState
from pdsh.api.routes_chat import router as chat_router
from pdsh.api.routes_sessions import router as sessions_router
from pdsh.api.schemas import HealthInfo
from pdsh.config import Settings
from pdsh.core.loop import AgentLoop
from pdsh.db.base import configure_snowflake
from pdsh.db.engine import create_engine_and_sessionmaker, init_schema
from pdsh.llm.base import LLMClient
from pdsh.llm.mock import MockLLM
from pdsh.llm.openai_compat import OpenAICompatClient
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore

_DEFAULT_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def build_llm(settings: Settings) -> LLMClient:
    """按配置构建 LLM 客户端（mock 用于无 key 开发与测试）。"""
    if settings.llm_provider == "mock":
        return MockLLM()
    return OpenAICompatClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        timeout=settings.llm_timeout,
    )


def create_app(
    settings: Settings | None = None,
    *,
    llm: LLMClient | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """应用工厂：装配引擎、仓储、注册表、LLM 与 AgentLoop。"""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_snowflake(settings.snowflake_worker_id)
        engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
        await init_schema(engine)
        ask_manager = AskUserManager()
        todo_store = TodoStore()
        registry = build_default_registry(settings, ask_manager, todo_store)
        llm_client = llm if llm is not None else build_llm(settings)
        store = SessionStore(sessionmaker, actor=settings.system_actor)
        loop = AgentLoop(
            llm=llm_client,
            registry=registry,
            store=store,
            max_iterations=settings.max_iterations,
            compaction_threshold=settings.compaction_threshold,
            workspace=str(Path(settings.workspace).resolve()),
        )
        application.state.pdsh = AppState(
            settings=settings,
            engine=engine,
            sessionmaker=sessionmaker,
            store=store,
            registry=registry,
            ask_manager=ask_manager,
            todo_store=todo_store,
            loop=loop,
        )
        try:
            yield
        finally:
            await _close_llm(llm_client)
            await engine.dispose()

    application = FastAPI(
        title="python-deepseek-harness",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(sessions_router)
    application.include_router(chat_router)

    @application.get("/healthz", response_model=HealthInfo)
    async def healthz() -> HealthInfo:
        return HealthInfo(version=__version__)

    _mount_frontend(application, static_dir or _DEFAULT_DIST)
    return application


async def _close_llm(llm_client: LLMClient) -> None:
    closer = getattr(llm_client, "aclose", None)
    if closer is not None:
        await closer()


def _mount_frontend(application: FastAPI, dist: Path) -> None:
    """托管前端构建产物（SPA 回退到 index.html）。"""
    index = dist / "index.html"
    if not index.is_file():
        return

    @application.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            return FileResponse(index)  # pragma: no cover
        candidate = (dist / path).resolve()
        if candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
