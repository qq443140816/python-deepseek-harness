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

"""OpenAI 兼容协议的 LLM 客户端（默认对接 DeepSeek 官方 API）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from pdsh.llm.types import ChatMessage, StreamEvent, ToolCall, ToolSpec, Usage

_CHAT_PATH = "/chat/completions"


class LLMError(RuntimeError):
    """LLM 调用失败。"""


class OpenAICompatClient:
    """OpenAI Chat Completions 兼容客户端，支持流式与 tool calling。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise LLMError("缺少 api_key，请配置 PDSH_API_KEY")
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _build_payload(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [self._message_to_wire(m) for m in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        return payload

    @staticmethod
    def _message_to_wire(message: ChatMessage) -> dict[str, object]:
        wire: dict[str, object] = {"role": message.role, "content": message.content}
        if message.tool_calls:
            wire["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in message.tool_calls
            ]
        if message.tool_call_id:
            wire["tool_call_id"] = message.tool_call_id
        return wire

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式对话；增量拼接后以事件形式产出。"""
        payload = self._build_payload(messages, tools)
        tool_acc: dict[int, dict[str, str]] = {}
        usage = Usage()
        try:
            async with self._client.stream("POST", _CHAT_PATH, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise LLMError(
                        f"LLM 接口返回 {resp.status_code}: "
                        f"{body[:300].decode('utf-8', 'replace')}"
                    )
                async for raw in resp.aiter_lines():
                    event = self._parse_chunk(raw, tool_acc, usage)
                    if event is not None:
                        yield event
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 网络错误: {exc}") from exc
        if tool_acc:
            yield StreamEvent(kind="tool_calls", tool_calls=self._finalize(tool_acc))
        yield StreamEvent(kind="done", usage=usage)

    @staticmethod
    def _parse_chunk(
        raw: str,
        tool_acc: dict[int, dict[str, str]],
        usage: Usage,
    ) -> StreamEvent | None:
        line = raw.strip()
        if not line.startswith("data:"):
            return None
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return None
        chunk = json.loads(data)
        if chunk.get("usage"):
            u = chunk["usage"]
            usage.prompt_tokens = u.get("prompt_tokens", 0)
            usage.completion_tokens = u.get("completion_tokens", 0)
        choices = chunk.get("choices") or []
        if not choices:
            return None
        delta = choices[0].get("delta") or {}
        if delta.get("reasoning_content"):
            return StreamEvent(kind="thinking_delta", delta=delta["reasoning_content"])
        if delta.get("tool_calls"):
            for tc in delta["tool_calls"]:
                idx = tc.get("index", 0)
                slot = tool_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] = fn["name"]
                slot["args"] += fn.get("arguments") or ""
            return None
        if delta.get("content"):
            return StreamEvent(kind="text_delta", delta=delta["content"])
        return None

    @staticmethod
    def _finalize(tool_acc: dict[int, dict[str, str]]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for idx in sorted(tool_acc):
            slot = tool_acc[idx]
            try:
                arguments = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                arguments = {"_raw": slot["args"]}
            calls.append(
                ToolCall(
                    id=slot["id"] or f"call_{idx}",
                    name=slot["name"],
                    arguments=arguments,
                )
            )
        return calls

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> str:
        """聚合流式输出为完整文本。"""
        parts: list[str] = []
        async for event in self.stream(messages, tools):
            if event.kind == "text_delta":
                parts.append(event.delta)
        return "".join(parts)
