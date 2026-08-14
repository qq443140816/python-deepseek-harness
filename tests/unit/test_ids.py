"""雪花 ID 生成器单元测试。"""

from __future__ import annotations

import pytest

from pdsh.ids import SnowflakeGenerator


def test_ids_unique_and_monotonic() -> None:
    gen = SnowflakeGenerator(worker_id=1)
    ids = [gen.next_id() for _ in range(5000)]
    assert len(set(ids)) == 5000
    assert ids == sorted(ids)


def test_worker_id_validation() -> None:
    with pytest.raises(ValueError):
        SnowflakeGenerator(worker_id=-1)
    with pytest.raises(ValueError):
        SnowflakeGenerator(worker_id=1024)
    assert SnowflakeGenerator(worker_id=0).worker_id == 0


def test_distinct_workers_produce_distinct_ids() -> None:
    a = SnowflakeGenerator(worker_id=1)
    b = SnowflakeGenerator(worker_id=2)
    assert a.next_id() != b.next_id()


def test_positive_64bit() -> None:
    gen = SnowflakeGenerator(worker_id=1)
    value = gen.next_id()
    assert 0 < value < (1 << 63)
