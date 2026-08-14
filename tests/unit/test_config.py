"""配置解析单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdsh.config import Settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-chat"
    assert settings.max_iterations == 25


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDSH_MODEL", "deepseek-reasoner")
    monkeypatch.setenv("PDSH_MAX_ITERATIONS", "7")
    settings = Settings(_env_file=None)
    assert settings.model == "deepseek-reasoner"
    assert settings.max_iterations == 7


def test_guardrail_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_iterations=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, tool_timeout=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, snowflake_worker_id=1024)
