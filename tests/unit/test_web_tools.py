"""web 工具单元测试：web_fetch（MockTransport）与 web_search（可插拔 provider）。"""

from __future__ import annotations

import httpx
import pytest

from pdsh.tools.base import ToolContext
from pdsh.tools.web_tools import (
    StubSearchProvider,
    WebFetchTool,
    WebSearchTool,
    _extract_text,
)


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(workspace=".", session_id=1)


def _fetch_tool(body: str, status: int = 200) -> WebFetchTool:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return WebFetchTool(transport=httpx.MockTransport(handler))


async def test_fetch_rejects_non_http(context: ToolContext) -> None:
    result = await WebFetchTool().run({"url": "ftp://x"}, context)
    assert result.is_error is True


async def test_fetch_extracts_text(context: ToolContext) -> None:
    html = (
        "<html><head><title>t</title><style>a{}</style></head>"
        "<body><script>bad()</script><p>正文一</p><div>正文二</div></body></html>"
    )
    tool = _fetch_tool(html)
    result = await tool.run({"url": "https://example.com"}, context)
    assert result.is_error is False
    assert "正文一" in result.output
    assert "正文二" in result.output
    assert "bad()" not in result.output


async def test_fetch_http_error(context: ToolContext) -> None:
    tool = _fetch_tool("not found", status=404)
    # 404 仍返回响应体；httpx 不抛异常，工具正常提取文本
    result = await tool.run({"url": "https://example.com/404"}, context)
    assert result.is_error is False


def test_extract_text_strips_tags() -> None:
    text = _extract_text("<p>甲</p><span>乙</span>")
    assert "甲" in text and "乙" in text
    assert "<" not in text


async def test_search_stub_provider(context: ToolContext) -> None:
    tool = WebSearchTool()
    result = await tool.run({"query": "合规尽调"}, context)
    assert result.is_error is False
    assert "未配置搜索服务" in result.output
    assert "合规尽调" in result.output


async def test_search_custom_provider(context: ToolContext) -> None:
    class FixedProvider:
        async def search(self, query: str, top_k: int) -> list[dict[str, str]]:
            return [
                {"title": f"结果{i}", "url": f"https://e.com/{i}", "snippet": "s"}
                for i in range(top_k)
            ]

    tool = WebSearchTool(FixedProvider())
    result = await tool.run({"query": "x", "top_k": 3}, context)
    assert result.is_error is False
    assert "结果0" in result.output and "结果2" in result.output


async def test_search_provider_empty(context: ToolContext) -> None:
    class EmptyProvider:
        async def search(self, query: str, top_k: int) -> list[dict[str, str]]:
            return []

    tool = WebSearchTool(EmptyProvider())
    result = await tool.run({"query": "x"}, context)
    assert result.output == "无搜索结果"


async def test_search_provider_raises(context: ToolContext) -> None:
    class BrokenProvider:
        async def search(self, query: str, top_k: int) -> list[dict[str, str]]:
            raise RuntimeError("网关不可用")

    tool = WebSearchTool(BrokenProvider())
    result = await tool.run({"query": "x"}, context)
    assert result.is_error is True
    assert "搜索失败" in result.output


async def test_stub_provider_returns_placeholder() -> None:
    items = await StubSearchProvider().search("q", 1)
    assert items[0]["title"].startswith("（占位）")
