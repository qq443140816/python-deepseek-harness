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

"""业务表模型：全部继承 BaseEntity（乐观锁 + 审计 + 软删除）。"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pdsh.db.base import BaseEntity


class SessionEntity(BaseEntity):
    """会话表。"""

    __tablename__ = "pdsh_session"

    title: Mapped[str] = mapped_column(
        String(256), default="", nullable=False, comment="会话标题"
    )


class SessionEventEntity(BaseEntity):
    """会话事件表：模型可见 ⟺ 已记录。"""

    __tablename__ = "pdsh_session_event"
    __table_args__ = (Index("idx_event_session", "session_id"),)

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pdsh_session.id"), nullable=False, comment="会话 ID"
    )
    event_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="事件类型"
    )
    payload: Mapped[str] = mapped_column(
        Text, default="", nullable=False, comment="事件负载 JSON"
    )


class TodoItemEntity(BaseEntity):
    """待办表。"""

    __tablename__ = "pdsh_todo_item"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pdsh_session.id"), nullable=False, comment="会话 ID"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="待办内容")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, comment="状态"
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False, comment="排序")


__all__ = ["SessionEntity", "SessionEventEntity", "TodoItemEntity"]
