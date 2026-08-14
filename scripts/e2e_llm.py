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

"""真实 LLM 端到端联调脚本。

读取 .env（PDSH_LLM_PROVIDER=openai 时使用真实 DeepSeek API），
用临时 SQLite 建会话，走完整 AgentLoop 发一轮消息，打印最终回复与事件摘要。
密钥不落日志。
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from pdsh.api.app import build_llm
from pdsh.config import Settings
from pdsh.core.loop import AgentLoop
from pdsh.db import models  # noqa: F401  导入即注册 metadata
from pdsh.db.base import configure_snowflake
from pdsh.db.engine import create_engine_and_sessionmaker, init_schema
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore

_PROMPT = "请用一句话介绍你自己"


async def main() -> None:
    settings = Settings()
    print(
        f"provider={settings.llm_provider} model={settings.model} "
        f"base={settings.base_url}"
    )
    if settings.llm_provider != "openai":
        print("当前 llm_provider 不是 openai，跳过真实 LLM 联调")
        return

    llm = build_llm(settings)
    configure_snowflake(settings.snowflake_worker_id)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            engine, maker = create_engine_and_sessionmaker(
                f"sqlite+aiosqlite:///{Path(tmp) / 'e2e.db'}"
            )
            await init_schema(engine)
            store = SessionStore(maker, actor=settings.system_actor)
            registry = build_default_registry(settings, AskUserManager(), TodoStore())
            loop = AgentLoop(
                llm=llm,
                registry=registry,
                store=store,
                max_iterations=settings.max_iterations,
                compaction_threshold=settings.compaction_threshold,
                workspace=str(Path(settings.workspace).resolve()),
            )
            session = await store.create_session("真实 LLM 联调")
            events = []
            async for event in loop.run_turn(session.id, _PROMPT):
                events.append(event)
            final = next(
                (
                    str(event.data.get("content", ""))
                    for event in reversed(events)
                    if event.kind == "done"
                ),
                "",
            )
            print("FINAL:", final)
            print("EVENTS:", [event.kind for event in events])
            await engine.dispose()
    finally:
        await llm.aclose()


if __name__ == "__main__":
    asyncio.run(main())
