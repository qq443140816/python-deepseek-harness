# Python DeepSeek Harness — 架构规划（Plan）

> 状态：**已实现**（2026-08-14）。规划经用户确认（含调整项），后端/前端/测试已按本规划落地，
> 全部质量门禁通过（black / isort / flake8 / mypy --strict / pytest 覆盖率 92.7% / bandit 零告警）。

## 1. 背景与目标

DeepSeek 官方开源的 deepseek-harness（`dsh`）是一个「一切皆插件」的 agent harness（TypeScript/Cordis），
核心为 agent-loop、tools、session、LLM capability seam 等通用能力，外加 LSP、代码沙箱等代码专用能力。

本项目目标：**用 Python 3.10 + FastAPI（后端）与 Vue 3 + Vite + TypeScript（前端）复刻其通用 agent 内核**，
去掉代码专用能力，作为企业自研 AI Agent harness 框架的基座。

- 项目名称：`python-deepseek-harness`（包名 `pdsh`）
- 许可证：MIT，Copyright (c) 2026 redfox <591006133@qq.com>
- 参考仓库：https://gitee.com/MrKoala/deepseek-harness

## 2. 能力裁剪决策（用户确认版）

### 2.1 保留：通用 agent 能力（对齐 dsh packages/core 等）

| dsh 原包 | 本仓库模块 | 说明 |
|---|---|---|
| `core/agent-loop`、`core/agent` | `pdsh/core/loop.py` | Agent 主循环：LLM → tool calls → 结果回填 → 直到收尾 |
| `core/tools` | `pdsh/tools/base.py` | 工具系统：注册表**对外开放**、JSON Schema 参数校验、超时、重复调用护栏 |
| `core/system-prompt` | `pdsh/core/prompt.py` | 系统提示词组装（基础人设 + 时间上下文 + 工具说明） |
| `core/session`、`session` | `pdsh/session` | 会话持久化（**MySQL**），「模型可见 ⟺ 已记录」事件模型 |
| `llm` | `pdsh/llm` | LLM 抽象层：**OpenAI 兼容协议**（默认 DeepSeek，base_url 可切企业私有网关） |
| `web`（search/fetch） | `pdsh/tools/web_tools.py` | `web_search`（provider 可插拔）+ `web_fetch` |
| `todo` | `pdsh/tools/todo.py` | `todo_write` 任务清单工具 |
| `interaction`（ask-user） | `pdsh/tools/ask_user.py` | `ask_user` 向用户提问并挂起等待回复 |
| `subagent` | `pdsh/subagent.py` | 子代理委派工具（受限工具集 + 独立上下文） |
| `compaction` | `pdsh/compaction.py` | 上下文压缩（超过 token 阈值时摘要历史） |
| `shell`、`subprocess` | `pdsh/tools/shell.py` | `shell` 命令执行工具（超时 + 工作目录限制） |
| `fs` | `pdsh/tools/fs.py` | 文件系统工具：read/write/edit/list/grep/glob（工作区根目录策略） |
| `acp` | `pdsh/acp` | **最小可用** ACP JSON-RPC（stdio）自动化服务端 |
| `settings`、`credentials` | `pdsh/config.py` | pydantic-settings 配置，`.env` 注入，密钥不落库不入日志 |
| Web UI | `web/` | **Vue 3 + Vite + TS**：会话侧边栏、聊天、SSE 流式、工具卡片 |

### 2.2 去掉：代码专用能力（收窄后）

| dsh 原包 | 剔除原因 |
|---|---|
| `lsp` | 语言服务器，纯代码场景 |
| `e2b`、`native/landlock-run`、code-runtime | 代码执行沙箱（企业侧自有沙箱接入） |
| `terminal`（持久终端会话）、diff 渲染、code mode、hunk diffs | 代码 diff/终端专用展示 |
| `hooks`（Claude Code/Codex 桥接）、`self-modification`、`workflow`、TUI | 非通用对话场景必需 |

**扩展点**：工具注册表对外公开，企业可按 `Tool` 协议自行挂接私有工具（审批流、知识库检索等）。

## 3. 目录结构

```
python-deepseek-harness/
├── AGENTS.md                  # Agent 开发规范（用户给定初版，原文落地）
├── LICENSE                    # MIT (redfox <591006133@qq.com>)
├── README.md
├── pyproject.toml             # PEP 621 + black/isort/mypy/pytest 配置
├── requirements.txt           # 运行时依赖锁定
├── requirements-dev.txt       # 开发依赖锁定
├── .gitignore
├── docs/
│   ├── PLAN.md                # 本文件
│   └── architecture.md        # 架构说明
├── src/pdsh/
│   ├── __init__.py
│   ├── config.py              # 配置（pydantic-settings）
│   ├── ids.py                 # 雪花 ID 生成器
│   ├── db/
│   │   ├── base.py            # MinimalEntity（雪花主键）/ BaseEntity（乐观锁+审计+软删）
│   │   ├── engine.py          # 异步引擎工厂（MySQL；测试用 aiosqlite）
│   │   └── models.py          # 业务表（均继承 BaseEntity）
│   ├── llm/
│   │   ├── types.py           # ChatMessage / ToolSpec / StreamEvent
│   │   ├── base.py            # LLMClient 协议
│   │   ├── openai_compat.py   # OpenAI 兼容实现（httpx.AsyncClient + SSE）
│   │   └── mock.py            # MockLLM（脚本化回放，contract test 用）
│   ├── core/
│   │   ├── events.py          # 会话事件模型
│   │   ├── prompt.py          # 系统提示词组装
│   │   └── loop.py            # AgentLoop（迭代上限/重复护栏/超时/ask_user 挂起）
│   ├── tools/
│   │   ├── base.py            # Tool 协议 + ToolRegistry + 校验/超时
│   │   ├── web_tools.py       # web_search / web_fetch
│   │   ├── todo.py            # todo_write
│   │   ├── ask_user.py        # ask_user
│   │   ├── shell.py           # shell 命令执行
│   │   ├── fs.py              # 文件系统工具集
│   │   └── builtin.py         # 默认注册表装配
│   ├── subagent.py            # 子代理委派
│   ├── compaction.py          # 上下文压缩
│   ├── session/
│   │   └── store.py           # 会话仓储（含 revision 乐观锁更新）
│   ├── api/
│   │   ├── schemas.py         # 请求/响应模型
│   │   ├── deps.py            # 依赖注入
│   │   ├── routes_sessions.py # 会话 CRUD
│   │   ├── routes_chat.py     # 对话（SSE 流式）+ ask_user 回复
│   │   └── app.py             # 应用工厂 + 前端静态托管
│   └── acp/
│       └── server.py          # 最小 ACP JSON-RPC（stdio）
├── tests/
│   ├── unit/                  # 不依赖外部服务（Mock LLM contract test 在此）
│   ├── integration/           # ASGI 接口测试（SQLite 内存库替代 MySQL）
│   ├── eval/                  # 行为评估（golden dataset）
│   ├── conftest.py
│   └── fixtures/
├── web/                       # Vue 3 + Vite + TS 前端
│   ├── package.json / vite.config.ts / tsconfig.json / index.html
│   └── src/                   # App.vue、会话侧边栏、聊天视图、工具卡片
└── scripts/
    └── pre-submit.ps1         # 一键门禁脚本
```

## 4. 关键设计

### 4.1 实体基类体系（用户要求）

```python
class MinimalEntity(Base):      # 最小实体基类：仅雪花主键
    id: Mapped[int]             # BIGINT 雪花 ID

class BaseEntity(MinimalEntity):  # 通用实体基类：所有业务表必须继承
    revision: int               # 乐观锁版本号，更新 +1 且校验
    created_by: str             # 创建人
    created_time: datetime      # 创建时间
    updated_by: str             # 更新人
    updated_time: datetime      # 更新时间
    is_deleted: int             # 软删除标记（0 正常 / 1 删除）
```

- 雪花 ID：`pdsh/ids.py` 实现（41bit 时间戳 + 10bit 机器位 + 12bit 序列号，线程安全）。
- 业务表：`pdsh_session`（会话）、`pdsh_session_event`（会话事件）、`pdsh_todo_item`（待办），全部继承 `BaseEntity`。
- 仓储层更新一律走 revision 乐观锁校验。

### 4.2 存储：MySQL（用户要求，替换 SQLite）

- SQLAlchemy 2.0 async + **aiomysql**；连接串 `PDSH_DB_URL` 配置，默认 `mysql+aiomysql://root:root@127.0.0.1:3306/pdsh`。
- 测试门禁不依赖真实 MySQL：集成测试用 `sqlite+aiosqlite` 内存库跑同一套 ORM 模型与仓储。
- 「模型可见 ⟺ 已记录」：所有模型可见内容以事件行落库，重放会话即重读事件流。

### 4.3 Agent Loop（对齐 dsh `agent-loop`）

```
user message → 组装上下文(系统提示+历史+工具schema) → LLM 流式调用
  → 有 tool_calls：逐个执行 → 结果写入会话事件 → 回到 LLM
  → 无 tool_calls：输出最终回复 → turn 结束
护栏：max_iterations(默认 25)、重复工具调用护栏、单工具超时(默认 60s)、ask_user 挂起/恢复
```

### 4.4 LLM 抽象（对齐 dsh capability seam）

- `LLMClient` 协议：`stream(messages, tools) -> AsyncIterator[StreamEvent]`、`complete(messages) -> str`。
- 默认实现走 OpenAI 兼容接口（DeepSeek 官方 API 即兼容），`base_url` 可配置，便于企业切换私有模型网关。
- 测试使用 `MockLLM` 脚本化回放，构成 contract test。

### 4.5 HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/sessions` | 新建会话 |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/{id}` | 会话详情（含事件流） |
| DELETE | `/api/sessions/{id}` | 删除会话（软删除） |
| POST | `/api/sessions/{id}/messages` | 发送消息，**SSE 流式**返回事件 |
| POST | `/api/sessions/{id}/responses` | 回复 `ask_user` 挂起的问题 |
| GET | `/api/tools` | 当前启用的工具清单 |
| GET | `/healthz` | 健康检查 |

SSE 事件类型：`text_delta` / `thinking_delta` / `tool_call` / `tool_result` / `ask_user` / `error` / `done`。

### 4.6 前端（Vue 3 + Vite + TS，用户选定）

- Vite 开发代理 `/api → 127.0.0.1:8000`；生产构建产物 `web/dist` 由 FastAPI 静态托管，单端口部署。
- 功能：会话侧边栏（新建/切换/删除）、聊天流式渲染、思考过程折叠、工具调用卡片（参数+结果+耗时）、`ask_user` 交互。

### 4.7 ACP（最小可用子集）

- stdio 上的 JSON-RPC 2.0：`initialize` / `session/new` / `session/prompt`（流式 update 通知）/ `session/cancel`。
- 入口：`python -m pdsh.acp`。文档明确标注为最小子集，后续按需对齐完整 ACP 规范。

### 4.8 配置（`.env`）

```
PDSH_API_KEY=...              # 必填，不落库
PDSH_BASE_URL=https://api.deepseek.com
PDSH_MODEL=deepseek-chat
PDSH_DB_URL=mysql+aiomysql://root:root@127.0.0.1:3306/pdsh
PDSH_WORKSPACE=./workspace    # shell/fs 工具的根目录边界
PDSH_MAX_ITERATIONS=25
PDSH_TOOL_TIMEOUT=60
PDSH_SNOWFLAKE_WORKER_ID=1
```

## 5. 风险点

- DeepSeek API 需要真实 key 才能端到端联调；无 key 时全部走 MockLLM 测试（CI 可跑）。
- 生产依赖真实 MySQL 实例；本地开发可用 Docker 一键起，测试走内存 SQLite。
- shell 工具存在命令执行风险：默认限制在工作区内且带超时，企业部署时应结合容器隔离。
- `web_search` 需要搜索服务供应商；默认提供接口与本地 stub，企业自行接入。

## 6. 验收标准（Definition of Done）

1. `pip install -r requirements.txt` 后 `uvicorn pdsh.api.app:app` 可启动并托管前端页面。
2. MockLLM 下完整跑通：多轮对话 → 工具调用 → ask_user 挂起恢复 → 上下文压缩 → 子代理委派。
3. 门禁通过：black / isort / flake8 / mypy --strict / pytest 覆盖率 ≥80% / bandit 零高中危。
4. AGENTS.md、README、LICENSE（MIT, redfox）齐备；前端 `npm run build` 通过。
