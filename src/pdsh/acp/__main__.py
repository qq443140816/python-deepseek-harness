"""ACP 入口：python -m pdsh.acp。"""

from __future__ import annotations

import asyncio

from pdsh.acp.server import AcpServer


def main() -> None:
    """stdio JSON-RPC 服务入口。"""
    asyncio.run(AcpServer().serve())


if __name__ == "__main__":
    main()
