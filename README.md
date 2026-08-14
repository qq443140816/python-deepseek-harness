# python-agent-harness

> 本仓库承载系统开发与运行：
>
> 1. **pdsh（python-deepseek-harness）**：根目录 `src/pdsh/` + `web/`。
>    通用 Agent harness 框架（FastAPI + Vue3），详见下方第一部分与 `docs/PLAN.pdsh.md`。

---
---


# Python DeepSeek Harness

企业自研通用 AI Agent harness 框架（python）。以 [DeepSeek Harness](https://gitee.com/MrKoala/deepseek-harness)（dsh）的通用 agent 内核为蓝本，用 **Python 3.10 + FastAPI**（后端）与 **Vue 3 + Vite + TypeScript**（前端）重新实现，剥离代码专用能力，保留通用 agent 能力。

## 架构总览

```
Vue3 前端 ──HTTP/SSE──> FastAPI ──> AgentLoop ──> LLM（OpenAI 兼容协议）
                          │             │
                       MySQL          ToolRegistry（shell/fs/web/todo/ask_user/subagent…）
```

核心原则（对齐 dsh）：

- **模型可见 ⟺ 已记录**：所有进入模型的上下文都以会话事件落库，可完整重放。
- **工具注册表对外开放**：企业可按 `Tool` 协议挂接私有工具（审批流、知识库等）。
- **capability seam**：LLM/存储/工具均为可替换抽象，默认实现面向 DeepSeek 官方 API（OpenAI 兼容）。

## 快速开始

```sh
# 1. 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
#    编辑 .env：PDSH_API_KEY / PDSH_DB_URL(MySQL) 等

# 3. 初始化数据库表（首次运行自动建表）并启动
uvicorn src.pdsh.api.app:app --host 127.0.0.1 --port 8000

# 4. 前端开发模式（另开终端）
cd web && npm install && npm run dev    # http://127.0.0.1:5173，代理 /api 到 8000
# 或生产构建：npm run build，产物 web/dist 由 FastAPI 直接托管（单端口）
```

浏览器访问 `http://127.0.0.1:8000`（生产）或 `http://127.0.0.1:5173`（开发）。

## 配置

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `PDSH_API_KEY` | LLM API Key（openai 模式必填，不落库不入日志） | — |
| `PDSH_BASE_URL` | OpenAI 兼容接口地址 | `https://api.deepseek.com` |
| `PDSH_MODEL` | 模型名 | `deepseek-chat` |
| `PDSH_LLM_PROVIDER` | `openai`（真实接口）/ `mock`（脚本回放，无 key 开发） | `openai` |
| `PDSH_DB_URL` | MySQL 连接串 | `mysql+aiomysql://root:root@127.0.0.1:3306/pdsh` |
| `PDSH_WORKSPACE` | shell/fs 工具工作区根目录 | `./workspace` |
| `PDSH_MAX_ITERATIONS` | 单轮最大 agent 迭代 | `25` |
| `PDSH_TOOL_TIMEOUT` | 单工具执行超时（秒） | `60` |
| `PDSH_SNOWFLAKE_WORKER_ID` | 雪花 ID 机器位 | `1` |

## 实体规范

所有业务表继承 `BaseEntity`（← `MinimalEntity`）：

- `MinimalEntity`：最小实体基类，仅雪花主键（BIGINT）。
- `BaseEntity`：`revision`（乐观锁）、`created_by` / `created_time` / `updated_by` / `updated_time`（审计）、`is_deleted`（软删除）。

## 开发

遵循 [AGENTS.md](AGENTS.md)：计划先行、测试门禁（pytest 覆盖率 ≥80%）、Mock LLM contract test、安全扫描。

```sh
pip install -r requirements-dev.txt
pytest tests/unit/ --cov=src/ --cov-fail-under=80   # 单元测试 + 覆盖率
pytest tests/integration/                          # ASGI 集成测试（内存 SQLite）
pytest tests/eval/ -v                              # 行为评估（golden dataset）

# 一键门禁（black/isort/flake8/mypy/pytest/bandit）
powershell -ExecutionPolicy Bypass -File scripts/pre-submit.ps1
```

- 架构与关键机制：[docs/architecture.md](docs/architecture.md)
- 规划与决策记录：[docs/PLAN.pdsh.md](docs/PLAN.pdsh.md)
- ACP（stdio JSON-RPC 最小子集）：`python -m pdsh.acp`

## 许可证

[MIT](LICENSE) © redfox <591006133@qq.com>

本项目是基于 DeepSeek Harness 通用能力的python版本独立重新实现，与 DeepSeek 官方仓库无代码级依赖。