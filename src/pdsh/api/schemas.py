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
