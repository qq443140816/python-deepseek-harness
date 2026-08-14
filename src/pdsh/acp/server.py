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

"""最小 ACP（Agent Client Protocol）JSON-RPC 服务端，stdio 传输。

实现子集（后续按需对齐完整 ACP 规范）：
- initialize：握手，返回协议版本与 agent 信息
- session/new：创建会话
- session/prompt：执行一轮对话，期间以 session/update 通知流式推送
- session/cancel：最小子集下仅确认收到（不支持中途打断 LLM）

传输约定：每行一个 JSON-RPC 2.0 对象（newline-delimited JSON）。
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from pdsh import __version__
from pdsh.config import Settings
from pdsh.core.loop import AgentLoop, LoopEvent
from pdsh.db.base import configure_snowflake
from pdsh.db.engine import create_engine_and_sessionmaker, init_schema
from pdsh.llm.base import LLMClient
from pdsh.session.store import SessionStore
from pdsh.tools.ask_user import AskUserManager
from pdsh.tools.builtin import build_default_registry
from pdsh.tools.todo import TodoStore

_PROTOCOL_VERSION = 1


class AcpServer:
    """stdio JSON-RPC 服务端。"""

    def __init__(
        self, settings: Settings | None = None, llm: LLMClient | None = None
    ) -> None:
        self._settings = settings or Settings()
        self._llm_override = llm
        self._loop: AgentLoop | None = None
        self._llm: LLMClient | None = None
        self._store: SessionStore | None = None
        self._engine: AsyncEngine | None = None

    async def setup(self) -> None:
        """初始化存储与 agent 栈。"""
        from pdsh.api.app import build_llm

        settings = self._settings
        configure_snowflake(settings.snowflake_worker_id)
        engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
        self._engine = engine
        await init_schema(engine)
        ask_manager = AskUserManager()
        todo_store = TodoStore()
        registry = build_default_registry(settings, ask_manager, todo_store)
        self._llm = self._llm_override or build_llm(settings)
        store = SessionStore(sessionmaker, actor=settings.system_actor)
        self._store = store
        self._loop = AgentLoop(
            llm=self._llm,
            registry=registry,
            store=store,
            max_iterations=settings.max_iterations,
            compaction_threshold=settings.compaction_threshold,
            workspace=str(settings.workspace),
        )

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    async def serve(self) -> None:
        """主循环：逐行读取 stdin 上的 JSON-RPC 请求。"""
        await self.setup()
        try:
            loop = asyncio.get_running_loop()
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                await self._handle_line(line)
        finally:
            await self.close()

    async def _handle_line(self, line: str) -> None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            self._send_error(None, -32700, "解析失败：非法 JSON")
            return
        method = message.get("method", "")
        request_id = message.get("id")
        params = message.get("params") or {}
        try:
            result = await self._dispatch(method, params)
        except KeyError as exc:
            self._send_error(request_id, -32602, f"缺少参数: {exc}")
            return
        except ValueError as exc:
            self._send_error(request_id, -32602, str(exc))
            return
        if request_id is not None:
            self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _loop_or_raise(self) -> AgentLoop:
        if self._loop is None:
            raise RuntimeError("ACP 服务未初始化")
        return self._loop

    def _store_or_raise(self) -> SessionStore:
        if self._store is None:
            raise RuntimeError("ACP 服务未初始化")
        return self._store

    async def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": _PROTOCOL_VERSION,
                "agentInfo": {"name": "pdsh", "version": __version__},
                "capabilities": {"prompt": {"streaming": True}},
            }
        if method == "session/new":
            return await self._session_new(params)
        if method == "session/prompt":
            await self._session_prompt(params)
            return {"stopReason": "end_turn"}
        if method == "session/cancel":
            return {}
        raise ValueError(f"不支持的方法: {method}")

    async def _session_new(self, params: dict[str, Any]) -> dict[str, Any]:
        store = self._store_or_raise()
        title = str(params.get("title", ""))
        entity = await store.create_session(title)
        return {"sessionId": str(entity.id)}

    async def _session_prompt(self, params: dict[str, Any]) -> None:
        loop = self._loop_or_raise()
        session_id = int(params["sessionId"])
        blocks = params.get("prompt") or []
        text = "\n".join(
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text:
            raise ValueError("prompt 中缺少 text 内容块")
        async for event in loop.run_turn(session_id, text):
            update = _to_acp_update(event)
            if update is not None:
                self._notify(
                    "session/update",
                    {"sessionId": str(session_id), "update": update},
                )

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send_error(self, request_id: Any, code: int, message: str) -> None:
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    @staticmethod
    def _send(payload: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _to_acp_update(event: LoopEvent) -> dict[str, Any] | None:
    """把 LoopEvent 映射为 ACP session/update 负载。"""
    data = event.data
    if event.kind == "text_delta":
        return {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": data.get("delta", "")},
        }
    if event.kind == "thinking_delta":
        return {
            "sessionUpdate": "agent_thought_chunk",
            "content": {"type": "text", "text": data.get("delta", "")},
        }
    if event.kind == "tool_call":
        return {
            "sessionUpdate": "tool_call",
            "toolCallId": data.get("call_id", ""),
            "title": str(data.get("name", "")),
            "status": "pending",
        }
    if event.kind == "tool_result":
        return {
            "sessionUpdate": "tool_call_update",
            "toolCallId": data.get("call_id", ""),
            "status": "failed" if data.get("is_error") else "completed",
            "content": [{"type": "text", "text": str(data.get("output", ""))}],
        }
    return None
