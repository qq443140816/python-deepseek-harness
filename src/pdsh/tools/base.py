"""工具系统核心：Tool 协议、注册表、Schema 校验与超时控制。

注册表对外开放：企业可按 Tool 协议注册私有工具。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from jsonschema import ValidationError, validate

from pdsh.llm.types import ToolSpec


class ToolError(RuntimeError):
    """工具执行失败（会作为 tool_result 回传给模型，不中断循环）。"""


@dataclass
class ToolContext:
    """工具执行上下文：工作区边界、当前会话标识。"""

    workspace: str
    session_id: int
    actor: str = "agent"
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """工具执行结果。"""

    output: str
    is_error: bool = False


@runtime_checkable
class Tool(Protocol):
    """工具协议：名称、描述、参数 Schema、异步执行。"""

    name: str
    description: str
    parameters: dict[str, Any]

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        """执行工具。参数已通过 Schema 校验。"""
        ...


class BaseTool:
    """工具基类：子类只需声明元信息并实现 _execute。"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._execute(arguments, context)

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        raise NotImplementedError

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class ToolRegistry:
    """工具注册表：校验、超时与未知工具处理。"""

    def __init__(self, timeout: float = 60.0) -> None:
        self._tools: dict[str, Tool] = {}
        self._timeout = timeout

    @property
    def timeout(self) -> float:
        return self._timeout

    def tools(self) -> list[Tool]:
        """按名称排序返回已注册工具实例。"""
        return [self._tools[name] for name in sorted(self._tools)]

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("工具必须有非空 name")
        if tool.name in self._tools:
            raise ValueError(f"工具重复注册: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """执行工具：未知工具/参数非法/超时/异常统一转 ToolResult。"""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(output=f"未知工具: {name}", is_error=True)
        try:
            validate(instance=arguments, schema=tool.parameters)
        except ValidationError as exc:
            return ToolResult(
                output=f"工具 {name} 参数校验失败: {exc.message}",
                is_error=True,
            )
        try:
            return await asyncio.wait_for(
                tool.run(arguments, context), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            return ToolResult(
                output=f"工具 {name} 执行超时（>{self._timeout}s）",
                is_error=True,
            )
        except ToolError as exc:
            return ToolResult(output=str(exc), is_error=True)
        except Exception as exc:  # noqa: BLE001 - 工具异常不应击穿 agent 循环
            return ToolResult(output=f"工具 {name} 执行异常: {exc}", is_error=True)
