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

"""API 请求/响应模型。

雪花主键为 64bit 整数，超出 JS Number 安全范围，
对外一律序列化为字符串。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def _id_to_str(value: int) -> str:
    return str(value)


class SessionCreate(BaseModel):
    """新建会话请求。"""

    title: str = ""


class SessionOut(BaseModel):
    """会话概要。"""

    id: str
    title: str
    revision: int
    created_time: datetime
    updated_time: datetime


class EventOut(BaseModel):
    """会话事件。"""

    id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_time: datetime


class SessionDetail(BaseModel):
    """会话详情（含事件流）。"""

    session: SessionOut
    events: list[EventOut]


class MessageRequest(BaseModel):
    """发送消息请求。"""

    content: str = Field(min_length=1)


class RespondRequest(BaseModel):
    """回复 ask_user 挂起问题。"""

    answer: str = Field(min_length=1)


class RespondResult(BaseModel):
    """ask_user 回复结果。"""

    resolved: bool


class ToolInfo(BaseModel):
    """工具清单条目。"""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class HealthInfo(BaseModel):
    """健康检查。"""

    status: str = "ok"
    version: str
