"""端到端冒烟脚本：以真实 HTTP 请求驱动运行中的 pdsh 服务。

用法：先设置环境变量（PDSH_LLM_PROVIDER=mock、PDSH_DB_URL=sqlite...）
启动 uvicorn pdsh.api.app:app，再运行本脚本。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def wait_ready(timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = _request("GET", "/healthz")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(0.3)
    raise SystemExit("服务未在超时时间内就绪")


def main() -> None:
    wait_ready()
    status, body = _request("GET", "/healthz")
    print("healthz:", status, body)
    assert status == 200

    status, body = _request("POST", "/api/sessions", {"title": "冒烟会话"})
    print("create session:", status, body[:120])
    assert status == 201
    session_id = json.loads(body)["id"]

    status, body = _request(
        "POST", f"/api/sessions/{session_id}/messages", {"content": "你好"}
    )
    print("messages SSE status:", status)
    assert status == 200
    events = [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    print("SSE events:", [e["type"] for e in events])
    assert events[-1]["type"] == "done"

    status, body = _request("GET", f"/api/sessions/{session_id}")
    detail = json.loads(body)
    print(
        "detail events:", [e["type"] for e in detail["events"]],
    )
    assert [e["type"] for e in detail["events"]] == ["user", "assistant"]

    status, body = _request("GET", "/api/tools")
    tools = json.loads(body)
    print("tools count:", len(tools))
    assert len(tools) >= 10

    status, body = _request("GET", "/")
    print("frontend index:", status, "pdsh" in body or "index" in body)
    assert status == 200 and "app" in body

    status, body = _request("DELETE", f"/api/sessions/{session_id}")
    print("delete:", status)
    assert status == 204

    print("SMOKE_OK")


if __name__ == "__main__":
    sys.exit(main())
