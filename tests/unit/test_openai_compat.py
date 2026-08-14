"""OpenAI 兼容客户端单元测试（httpx.MockTransport 驱动）。"""

from __future__ import annotations

import json

import httpx
import pytest

from pdsh.llm.openai_compat import LLMError, OpenAICompatClient
from pdsh.llm.types import ChatMessage


def _sse_body(chunks: list[dict[str, object]]) -> str:
    lines = [f"data: {json.dumps(chunk)}" for chunk in chunks]
    lines.append("data: [DONE]")
    return "\n".join(lines) + "\n"


def _client_with_body(body: str, status: int = 200) -> OpenAICompatClient:
    client = OpenAICompatClient("key", "http://mock", "deepseek-chat")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    # 测试替换底层 transport；不产生真实网络请求
    client._client = httpx.AsyncClient(  # noqa: SLF001
        transport=httpx.MockTransport(handler), base_url="http://mock"
    )
    return client


def test_missing_api_key() -> None:
    with pytest.raises(LLMError):
        OpenAICompatClient("", "http://mock", "m")


async def test_stream_text_and_usage() -> None:
    body = _sse_body(
        [
            {"choices": [{"delta": {"content": "你"}}]},
            {"choices": [{"delta": {"content": "好"}}]},
            {
                "choices": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        ]
    )
    client = _client_with_body(body)
    events = [
        event async for event in client.stream([ChatMessage(role="user", content="hi")])
    ]
    kinds = [e.kind for e in events]
    assert kinds == ["text_delta", "text_delta", "done"]
    assert events[-1].usage.completion_tokens == 2
    text = await client.complete([ChatMessage(role="user", content="hi")])
    assert text == "你好"
    await client.aclose()


async def test_stream_reasoning_content() -> None:
    body = _sse_body(
        [
            {"choices": [{"delta": {"reasoning_content": "先分析"}}]},
            {"choices": [{"delta": {"content": "答案"}}]},
        ]
    )
    client = _client_with_body(body)
    events = [
        event async for event in client.stream([ChatMessage(role="user", content="q")])
    ]
    assert events[0].kind == "thinking_delta"
    assert events[0].delta == "先分析"
    await client.aclose()


async def test_stream_tool_calls_accumulation() -> None:
    body = _sse_body(
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {
                                        "name": "fs_read",
                                        "arguments": '{"path":',
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '"a.txt"}'},
                                }
                            ]
                        }
                    }
                ]
            },
        ]
    )
    client = _client_with_body(body)
    events = [
        event async for event in client.stream([ChatMessage(role="user", content="q")])
    ]
    tool_event = events[0]
    assert tool_event.kind == "tool_calls"
    call = tool_event.tool_calls[0]
    assert call.name == "fs_read"
    assert call.arguments == {"path": "a.txt"}
    await client.aclose()


async def test_stream_invalid_json_args_fallback() -> None:
    body = _sse_body(
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c",
                                    "function": {
                                        "name": "t",
                                        "arguments": "{broken",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    )
    client = _client_with_body(body)
    events = [
        event async for event in client.stream([ChatMessage(role="user", content="q")])
    ]
    assert events[0].tool_calls[0].arguments == {"_raw": "{broken"}
    await client.aclose()


async def test_http_error_raises_llm_error() -> None:
    client = _client_with_body('{"error": "denied"}', status=401)
    with pytest.raises(LLMError):
        async for _ in client.stream([ChatMessage(role="user", content="q")]):
            pass
    await client.aclose()


def test_message_to_wire_with_tool_fields() -> None:
    from pdsh.llm.types import ToolCall

    message = ChatMessage(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="c1", name="shell", arguments={"command": "ls"})],
    )
    wire = OpenAICompatClient._message_to_wire(message)  # noqa: SLF001
    assert wire["tool_calls"][0]["function"]["name"] == "shell"

    tool_message = ChatMessage(
        role="tool", content="ok", tool_call_id="c1", name="shell"
    )
    wire2 = OpenAICompatClient._message_to_wire(tool_message)  # noqa: SLF001
    assert wire2["tool_call_id"] == "c1"
