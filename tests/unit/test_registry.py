"""工具注册表单元测试：校验、超时、异常兜底。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pdsh.tools.base import (
    BaseTool,
    ToolContext,
    ToolError,
    ToolRegistry,
    ToolResult,
)


class EchoTool(BaseTool):
    name = "echo"
    description = "回显输入"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        return ToolResult(output=arguments["text"])


class BoomTool(BaseTool):
    name = "boom"
    description = "必然抛异常"
    parameters = {"type": "object", "properties": {}}

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        raise RuntimeError("内部爆炸")


class SlowTool(BaseTool):
    name = "slow"
    description = "睡眠工具"
    parameters = {"type": "object", "properties": {}}

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        await asyncio.sleep(1)
        return ToolResult(output="ok")


class ToolErrorTool(BaseTool):
    name = "soft_fail"
    description = "软失败"
    parameters = {"type": "object", "properties": {}}

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        raise ToolError("业务错误")


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(workspace=".", session_id=1)


def test_register_and_lookup() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.names() == ["echo"]
    assert registry.get("echo") is not None
    assert registry.get("nope") is None
    specs = registry.specs()
    assert specs[0].name == "echo"
    assert registry.timeout == 60.0


def test_register_rejects_duplicate_and_empty() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ValueError):
        registry.register(EchoTool())

    class Nameless(BaseTool):
        name = ""

    with pytest.raises(ValueError):
        registry.register(Nameless())


async def test_execute_ok(context: ToolContext) -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    result = await registry.execute("echo", {"text": "hi"}, context)
    assert result.output == "hi"
    assert result.is_error is False


async def test_execute_unknown(context: ToolContext) -> None:
    registry = ToolRegistry()
    result = await registry.execute("ghost", {}, context)
    assert result.is_error is True
    assert "未知工具" in result.output


async def test_execute_schema_violation(context: ToolContext) -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    result = await registry.execute("echo", {"text": 123}, context)
    assert result.is_error is True
    assert "参数校验失败" in result.output


async def test_execute_timeout(context: ToolContext) -> None:
    registry = ToolRegistry(timeout=0.05)
    registry.register(SlowTool())
    result = await registry.execute("slow", {}, context)
    assert result.is_error is True
    assert "超时" in result.output


async def test_execute_exception_caught(context: ToolContext) -> None:
    registry = ToolRegistry()
    registry.register(BoomTool())
    result = await registry.execute("boom", {}, context)
    assert result.is_error is True
    assert "异常" in result.output


async def test_execute_tool_error(context: ToolContext) -> None:
    registry = ToolRegistry()
    registry.register(ToolErrorTool())
    result = await registry.execute("soft_fail", {}, context)
    assert result.is_error is True
    assert result.output == "业务错误"
