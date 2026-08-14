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

"""雪花 ID 生成器。

64bit 结构：1bit 符号位 + 41bit 毫秒时间戳 + 10bit 机器位 + 12bit 序列号。
对应实体规范中 MinimalEntity 的雪花主键。
"""

from __future__ import annotations

import threading
import time

#: 自定义纪元（毫秒）：2023-11-14T22:13:20Z
_EPOCH_MS = 1_700_000_000_000
_WORKER_BITS = 10
_SEQUENCE_BITS = 12
_MAX_WORKER_ID = (1 << _WORKER_BITS) - 1
_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1
_WORKER_SHIFT = _SEQUENCE_BITS
_TIME_SHIFT = _WORKER_BITS + _SEQUENCE_BITS


class SnowflakeGenerator:
    """线程安全的雪花 ID 生成器。"""

    def __init__(self, worker_id: int = 1) -> None:
        if not 0 <= worker_id <= _MAX_WORKER_ID:
            raise ValueError(
                f"worker_id 必须在 0..{_MAX_WORKER_ID} 之间，实际为 {worker_id}"
            )
        self._worker_id = worker_id
        self._sequence = 0
        self._last_ts = -1
        self._lock = threading.Lock()

    @property
    def worker_id(self) -> int:
        return self._worker_id

    def next_id(self) -> int:
        """生成下一个全局唯一的雪花 ID。"""
        with self._lock:
            ts = self._current_ms()
            if ts < self._last_ts:
                # 时钟回拨：沿用上次的毫秒位继续发号，避免 ID 倒退
                ts = self._last_ts
            if ts == self._last_ts:
                self._sequence = (self._sequence + 1) & _MAX_SEQUENCE
                if self._sequence == 0:
                    ts = self._wait_next_ms(ts)
            else:
                self._sequence = 0
            self._last_ts = ts
            return (
                ((ts - _EPOCH_MS) << _TIME_SHIFT)
                | (self._worker_id << _WORKER_SHIFT)
                | self._sequence
            )

    @staticmethod
    def _current_ms() -> int:
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_ts: int) -> int:
        ts = self._current_ms()
        while ts <= last_ts:
            ts = self._current_ms()
        return ts
