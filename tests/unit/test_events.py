"""事件模型与重放单元测试。"""

from __future__ import annotations

import pytest

from pdsh.core.events import EventType, SessionEvent, replay_messages


def test_dump_load_roundtrip() -> None:
    event = SessionEvent(
        type=EventType.TOOL_CALL,
        payload={
            "calls": [{"id": "c1", "name": "fs_read", "arguments": {"path": "a.txt"}}]
        },
    )
    restored = SessionEvent.load(event.dump())
    assert restored == event


def test_load_invalid_type() -> None:
    with pytest.raises(ValueError):
        SessionEvent.load('{"type": "ghost", "payload": {}}')


def test_replay_basic_flow() -> None:
    events = [
        SessionEvent(type=EventType.USER, payload={"content": "写文件"}),
        SessionEvent(
            type=EventType.TOOL_CALL,
            payload={
                "calls": [
                    {
                        "id": "c1",
                        "name": "fs_write",
                        "arguments": {"path": "a.txt", "content": "x"},
                    }
                ]
            },
        ),
        SessionEvent(
            type=EventType.TOOL_RESULT,
            payload={"call_id": "c1", "name": "fs_write", "output": "已写入"},
        ),
        SessionEvent(type=EventType.THINKING, payload={"content": "思考"}),
        SessionEvent(type=EventType.ASSISTANT, payload={"content": "完成"}),
        SessionEvent(type=EventType.SYSTEM_NOTE, payload={"content": "审计"}),
    ]
    messages = replay_messages(events)
    roles = [m.role for m in messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert messages[1].tool_calls[0].name == "fs_write"
    assert messages[2].tool_call_id == "c1"
    assert messages[2].content == "已写入"


def test_replay_compaction_resets_history() -> None:
    events = [
        SessionEvent(type=EventType.USER, payload={"content": "早期问题"}),
        SessionEvent(type=EventType.ASSISTANT, payload={"content": "早期回答"}),
        SessionEvent(type=EventType.COMPACTION, payload={"summary": "摘要 X"}),
        SessionEvent(type=EventType.USER, payload={"content": "新问题"}),
    ]
    messages = replay_messages(events)
    assert len(messages) == 2
    assert "摘要 X" in messages[0].content
    assert messages[1].content == "新问题"
