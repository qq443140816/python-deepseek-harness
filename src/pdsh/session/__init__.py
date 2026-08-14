"""会话子包：会话与事件的持久化仓储。"""

from pdsh.session.store import SessionStore, StaleRevisionError

__all__ = ["SessionStore", "StaleRevisionError"]
