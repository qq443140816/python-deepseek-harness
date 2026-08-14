"""系统提示词组装单元测试。"""

from __future__ import annotations

from datetime import datetime

from pdsh.core.prompt import build_system_prompt


def test_prompt_contains_persona_and_tools() -> None:
    prompt = build_system_prompt(
        tool_names=["fs_read", "shell"],
        now=datetime(2026, 8, 14, 10, 30),
    )
    assert "pdsh" in prompt
    assert "fs_read, shell" in prompt
    assert "2026-08-14 10:30" in prompt


def test_prompt_without_tools() -> None:
    prompt = build_system_prompt(tool_names=[])
    assert "可用工具" not in prompt
    assert "通用 AI 助手" in prompt
