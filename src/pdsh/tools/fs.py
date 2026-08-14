"""文件系统工具集：read / write / edit / list / grep / glob。

所有路径被约束在 context.workspace 之内（防路径穿越）。
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from pdsh.tools.base import BaseTool, ToolContext, ToolError, ToolResult

_MAX_OUTPUT_CHARS = 20_000


def _resolve_safe(workspace: str, rel_path: str) -> Path:
    """把工作区内相对路径解析为绝对路径，越界即报错。"""
    root = Path(workspace).resolve()
    target = (root / rel_path).resolve()
    if target != root and root not in target.parents:
        raise ToolError(f"路径越出工作区: {rel_path}")
    return target


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + "\n...[内容过长已截断]"


class ReadFileTool(BaseTool):
    name = "fs_read"
    description = "读取工作区内文本文件内容"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        target = _resolve_safe(context.workspace, arguments["path"])
        if not target.is_file():
            return ToolResult(output=f"文件不存在: {arguments['path']}", is_error=True)
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(output=f"读取失败: {exc}", is_error=True)
        return ToolResult(output=_truncate(text))


class WriteFileTool(BaseTool):
    name = "fs_write"
    description = "写入（覆盖）工作区内文件，自动创建父目录"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        target = _resolve_safe(context.workspace, arguments["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(arguments["content"], encoding="utf-8")
        return ToolResult(output=f"已写入 {arguments['path']}")


class EditFileTool(BaseTool):
    name = "fs_edit"
    description = "精确替换文件中的一段文本（old 必须唯一存在）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old": {"type": "string"},
            "new": {"type": "string"},
        },
        "required": ["path", "old", "new"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        target = _resolve_safe(context.workspace, arguments["path"])
        if not target.is_file():
            return ToolResult(output="文件不存在", is_error=True)
        text = target.read_text(encoding="utf-8")
        old: str = arguments["old"]
        count = text.count(old)
        if count != 1:
            return ToolResult(
                output=f"匹配到 {count} 处（需恰好 1 处），请调整 old 内容",
                is_error=True,
            )
        target.write_text(text.replace(old, arguments["new"]), encoding="utf-8")
        return ToolResult(output="替换完成")


class ListDirTool(BaseTool):
    name = "fs_list"
    description = "列出目录内容（目录优先，递归可选）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "recursive": {"type": "boolean", "default": False},
        },
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        root = _resolve_safe(context.workspace, arguments.get("path", "."))
        if not root.is_dir():
            return ToolResult(output="目录不存在", is_error=True)
        entries: list[str] = []
        iterator = root.rglob("*") if arguments.get("recursive") else root.iterdir()
        for item in iterator:
            rel = item.relative_to(root)
            entries.append(f"{rel}/" if item.is_dir() else str(rel))
            if len(entries) >= 500:
                entries.append("...[列表过长已截断]")
                break
        return ToolResult(output="\n".join(sorted(entries)) or "(空目录)")


class GlobTool(BaseTool):
    name = "fs_glob"
    description = "按通配符模式查找工作区内文件"
    parameters = {
        "type": "object",
        "properties": {"pattern": {"type": "string"}},
        "required": ["pattern"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        root = Path(context.workspace).resolve()
        matches = [
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file()
            and fnmatch.fnmatch(str(p.relative_to(root)), arguments["pattern"])
        ]
        return ToolResult(
            output=_truncate("\n".join(sorted(matches)[:200])) or "(无匹配)"
        )


class GrepTool(BaseTool):
    name = "fs_grep"
    description = "在工作区文本文件中搜索子串（区分大小写）"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
        },
        "required": ["pattern"],
    }

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        root = _resolve_safe(context.workspace, arguments.get("path", "."))
        pattern: str = arguments["pattern"]
        hits: list[str] = []
        for file in root.rglob("*"):
            if not file.is_file() or file.stat().st_size > 1_000_000:
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern in line:
                    hits.append(f"{file.relative_to(root)}:{lineno}: {line.strip()}")
                    if len(hits) >= 100:
                        return ToolResult(output=_truncate("\n".join(hits)))
        return ToolResult(output=_truncate("\n".join(hits)) or "(无匹配)")
