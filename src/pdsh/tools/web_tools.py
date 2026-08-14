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

"""Web 工具：web_fetch（抓取网页正文）与 web_search（provider 可插拔）。

web_search 默认提供离线 stub；企业可注入自有搜索 provider。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import httpx

from pdsh.tools.base import BaseTool, ToolContext, ToolResult

_MAX_FETCH_CHARS = 20_000


@runtime_checkable
class SearchProvider(Protocol):
    """搜索服务供应商协议：返回结果条目列表。"""

    async def search(self, query: str, top_k: int) -> list[dict[str, str]]: ...


class StubSearchProvider:
    """默认占位 provider：提示接入真实搜索服务。"""

    async def search(self, query: str, top_k: int) -> list[dict[str, str]]:
        return [
            {
                "title": "（占位）未配置搜索服务",
                "url": "",
                "snippet": (
                    f"query={query}。请在装配注册表时注入真实 "
                    "SearchProvider（企业搜索网关）。"
                ),
            }
        ]


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "抓取指定 URL 的网页文本内容（纯文本提取）"
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    }

    def __init__(
        self,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout
        self._transport = transport

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        url: str = arguments["url"]
        if not url.startswith(("http://", "https://")):
            return ToolResult(output="仅支持 http/https URL", is_error=True)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                transport=self._transport,
            ) as client:
                resp = await client.get(url)
        except httpx.HTTPError as exc:
            return ToolResult(output=f"抓取失败: {exc}", is_error=True)
        text = _extract_text(resp.text)
        return ToolResult(output=text[:_MAX_FETCH_CHARS])


def _extract_text(html: str) -> str:
    """轻量 HTML→文本提取（不引入额外依赖）。"""
    import re

    body = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?s)<[^>]+>", "\n", body)
    lines = [ln.strip() for ln in body.splitlines()]
    return "\n".join(ln for ln in lines if ln)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网信息，返回标题/链接/摘要列表"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
    }

    def __init__(self, provider: SearchProvider | None = None) -> None:
        self._provider = provider or StubSearchProvider()

    async def _execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        try:
            items = await self._provider.search(
                arguments["query"], int(arguments.get("top_k", 5))
            )
        except Exception as exc:  # noqa: BLE001 搜索供应商异常转工具错误
            return ToolResult(output=f"搜索失败: {exc}", is_error=True)
        if not items:
            return ToolResult(output="无搜索结果")
        lines = [
            f"{i}. {it.get('title', '')}\n   {it.get('url', '')}\n"
            f"   {it.get('snippet', '')}"
            for i, it in enumerate(items, 1)
        ]
        return ToolResult(output="\n".join(lines))
