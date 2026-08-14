# 架构说明

> 规划与决策见 [PLAN.md](PLAN.md)，本文描述落地后的模块关系与关键机制。

## 分层结构

```
web/（Vue3+Vite+TS）
  └─ fetch/SSE
       │
src/pdsh/
  api/        FastAPI 路由 + SSE + 静态托管（app.py 应用工厂）
  core/       AgentLoop 主循环、事件模型（events）、系统提示词（prompt）
  session/    会话仓储（revision 乐观锁 + 事件流读写）
  db/         MinimalEntity/BaseEntity 实体基类、异步引擎、业务表
  llm/        LLMClient 协议、OpenAI 兼容实现、MockLLM
  tools/      Tool 协议 + 注册表 + 内置工具（fs/shell/web/todo/ask_user）
  subagent.py 子代理委派（受限工具集的独立循环）
  compaction.py 上下文压缩
  acp/        最小 ACP JSON-RPC（stdio）
```

## 关键机制

### 1. 模型可见 ⟺ 已记录

`AgentLoop` 不把历史保存在内存里：每一步（用户消息、助手回复、工具调用、
工具结果、压缩摘要）都通过 `SessionStore.append_event` 落库为事件行。
下一次迭代前由 `replay_messages` 重放事件流组装模型上下文。
进程重启、多实例部署都不丢失对话状态。

### 2. Agent Loop 护栏

| 护栏 | 实现位置 | 行为 |
|---|---|---|
| 迭代上限 | `AgentLoop.run_turn` | 超过 `max_iterations` 记 SYSTEM_NOTE 并终止 |
| 重复调用 | `AgentLoop._run_one_tool` | 同参数同工具超过 2 次拒绝执行并回错 |
| 工具超时 | `ToolRegistry.execute` | `asyncio.wait_for` 包裹，超时转错误结果 |
| ask_user 挂起 | `AskUserManager` | Future 挂起；`POST /responses` 唤醒；断开即取消 |
| 上下文膨胀 | `compaction.maybe_compact` | 超阈值摘要旧历史并落 COMPACTION 事件 |

### 3. SSE 事件协议

`POST /api/sessions/{id}/messages` 返回 `text/event-stream`，每帧
`data: {JSON}\n\n`，事件类型：

`text_delta` / `thinking_delta` / `tool_call` / `tool_result` / `ask_user` /
`done` / `error`。前端 `web/src/api.ts` 的 `streamMessage` 消费该协议。

### 4. 实体与乐观锁

`MinimalEntity`（雪花主键）← `BaseEntity`（revision/审计/软删除）。
仓储层更新会话（改标题、软删除）必须携带读到的 `revision`，
`UPDATE ... WHERE id=? AND revision=?` 影响行数为 0 即抛
`StaleRevisionError`（API 转 409）。雪花 ID 超过 JS 安全整数范围，
API 层一律序列化为字符串。

### 5. 扩展点

- **私有工具**：实现 `Tool` 协议后经 `build_default_registry(extra_tools=...)`
  或 `ToolRegistry.register` 挂接。
- **搜索供应商**：`WebSearchTool(provider=...)` 注入企业搜索网关。
- **LLM 网关**：`PDSH_BASE_URL` 指向 OpenAI 兼容的企业私有网关即可。
- **ACP 集成**：`python -m pdsh.acp` 提供 stdio JSON-RPC 最小子集。
