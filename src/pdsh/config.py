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

"""应用配置：pydantic-settings 驱动，环境变量 / .env 注入。

密钥类字段（api_key）不落库、不入日志。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """pdsh 全量配置，环境变量前缀 PDSH_。"""

    model_config = SettingsConfigDict(
        env_prefix="PDSH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM（OpenAI 兼容协议，默认 DeepSeek 官方 API）
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    llm_provider: Literal["openai", "mock"] = "openai"
    llm_timeout: float = 120.0

    # 存储（MySQL；测试环境可注入 sqlite+aiosqlite）
    db_url: str = "mysql+aiomysql://root:root@127.0.0.1:3306/pdsh"

    # Agent 行为护栏
    max_iterations: int = Field(default=25, ge=1)
    tool_timeout: float = Field(default=60.0, gt=0)
    ask_user_timeout: float = Field(default=600.0, gt=0)
    compaction_threshold: int = Field(default=8000, ge=1)

    # shell / fs 工具的工作区边界
    workspace: Path = Path("workspace")

    # web_search 默认搜索 provider（bing 为无 key 网页搜索；stub 为占位）
    search_provider: Literal["bing", "stub"] = "bing"
    search_timeout: float = Field(default=10.0, gt=0)

    # 雪花 ID 机器位
    snowflake_worker_id: int = Field(default=1, ge=0, le=1023)

    # 审计字段默认操作人
    system_actor: str = "system"
