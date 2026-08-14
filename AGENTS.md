# AGENTS.md —— 仓库 Agent 开发规范（合订本）

> 本仓库同时承载两条开发线，规范按适用范围划为两部分：
>
> - **第一部分（pdsh / python-deepseek-harness）**：适用于根目录 `src/pdsh/`、`tests/`、
>   `web/`（Vue3 单页）、`scripts/`。项目名 python-deepseek-harness 为用户明确指定，
>   属公开复刻声明（MIT、致谢上游），不受第二部分命名红线条款约束。
> - **第二部分（Python Agent Harness 框架 / RedFox Agent）**：适用于 `src/backend/`、
>   `src/frontend/`、`docker/`。
>
> 两部分冲突时以各自适用范围为准；MIT 许可、密钥不落库、改码必测为全仓库共同红线。

---
---


# AGENTS.md

本文件定义了 Agent（Coding Agent / AI Assistant）在本仓库中的行为准则、开发规范与提交流程。Agent 在开始任何任务前必须先读取本文件。

支持语言：Python、TypeScript/JavaScript、Go、Java、Rust 等主流语言。本文档以 Python 为例提供详细配置，其他语言请参照执行。

## 一、核心指令

### 1.1 第一原则

在开始任何任务之前，必须先读取 AGENTS.md 和 .cursorrules（如存在）。

### 1.2 工作模式

你是一个严谨的工程师 Agent，不是聊天助手。你的输出必须是：

- 可验证的（有测试证据）
- 可追溯的（有 commit 记录）
- 可回滚的（有分支策略）

### 1.3 禁止行为

- ❌ 不读规范就直接写代码
- ❌ 不写测试就提交
- ❌ 不跑 eval 就开 PR
- ❌ 修改 AGENTS.md 自身（除非有明确 Issue 授权）
- ❌ 在代码中留下调试语句（print()、logging.debug 未清理、TODO 遗留）
- ❌ 提交虚拟环境目录（venv、.venv、__pycache__、*.pyc）

## 二、任务启动流程

### 2.1 任务准入检查

在开始编码前，你必须检查 Issue/Task 是否包含以下信息。缺失任何一项，停止编码并向用户提问：

- [ ] 背景与目标
- [ ] 改动范围（改什么 / 不改什么）
- [ ] 验收标准
- [ ] 参考文件 / 历史 PR / 设计文档
- [ ] 必须跑的测试命令
- [ ] 需要新增的测试类型
- [ ] 允许自动执行的步骤 vs 需要人工确认的步骤
- [ ] 最大自修复次数（默认 3）

### 2.2 分支创建

- 从最新的 main 分支切出
- 分支名格式：feature/agent-{issue_id}-{kebab-case描述}
- 示例：feature/agent-PROJ-1234-add-rate-limit

## 三、开发规范

### 3.1 计划先行

在写任何代码之前，先输出实现计划：

```
## Plan

### 改动文件列表

- src/middleware/rate_limit.py（新建）
- src/main.py（修改，注册中间件）
- tests/test_rate_limit.py（新建）

### 改动内容

1. 新建 RateLimitMiddleware 类，基于 Token Bucket 算法
2. 支持配置每秒请求数（RPS）和 burst 大小
3. 返回 429 状态码时附带 Retry-After 头

### 风险点

- 需要 Redis 实例，本地测试用 mock
- 首次接入可能影响现有路由的延迟

### 不这么改的风险

- 不做限流，恶意请求可能导致服务雪崩
```

复杂变更（跨模块/改架构/涉及安全）必须等人确认后再执行。

### 3.2 代码编写规范

#### 文件大小限制

- 单个 Python 文件不超过 300 行（不含注释和空行）
- 超出需拆分为多个模块或包

#### Python 代码风格

- 遵循 PEP 8 规范
- 类型注解必须完整（使用 typing 模块）
- 使用 black 格式化（line-length=88）
- 使用 isort 排序 import（5 个分组：标准库 → 第三方 → 本地 → 相对导入 → 类型导入）
- 禁止使用 from module import *
- 字符串优先使用 f-string

#### 测试要求

- 每新增一个功能，必须对应新增至少一个测试用例
- 测试框架：pytest（统一使用）
- 测试文件命名：test_*.py 或 *_test.py
- 测试目录结构：

```
tests/
  unit/          # 单元测试（不依赖外部服务）
  integration/   # 集成测试（依赖 DB/Redis/API）
  eval/          # 行为评估（Agent 类项目专用）
  conftest.py    # 共享 fixture
  fixtures/      # 测试数据文件（JSON/YAML）
```

- 对于 Agent 类代码，必须包含 Mock LLM 的 contract test

#### 依赖管理

- 使用 pip-tools 或 poetry 管理依赖
- 主依赖写入 requirements.in 或 pyproject.toml 的 [tool.poetry.dependencies]
- 开发依赖写入 requirements-dev.in 或 [tool.poetry.group.dev.dependencies]
- 锁定文件：requirements.txt / poetry.lock 必须提交
- 禁止：直接 pip install xxx 后不更新锁定文件

#### 异步编程规范

- 优先使用 async/await 而非回调
- 异步测试使用 pytest-asyncio
- HTTP 客户端统一使用 httpx.AsyncClient
- 数据库驱动使用异步版本（如 asyncpg、aiomysql、motor）

### 3.3 Commit Message 格式

```
feat(scope): 一句话说明

- 改了什么
- 为什么这么改
- 测试证据：单元测试通过 / eval 分数未下降
```

禁止的 Commit Message：fix bug、update、wip、asdf

## 四、自检门禁（Pre-submit）

每次提交前，你必须依次执行以下检查。任何一项失败，不得提交。

### 4.1 确定性测试（必须 100% 通过）

```sh
# Python 项目
poetry run black --check src/ tests/            # 代码格式化检查
poetry run isort --check-only src/ tests/       # import 排序检查
poetry run flake8 src/ tests/                   # PEP 8 检查（max-line-length=88）
poetry run mypy src/                            # 类型检查（严格模式）
poetry run pytest tests/unit/ --cov=src/ --cov-fail-under=80  # 单元测试 + 覆盖率
poetry run pytest tests/integration/            # 集成测试
```

各检查项的通过条件：

| 检查项 | 命令 | 通过条件 |
|--------|------|----------|
| 代码格式化 | black --check | 零差异 |
| Import 排序 | isort --check-only | 零差异 |
| PEP 8 检查 | flake8 | 零 error，零 warning |
| 类型检查 | mypy --strict | 零 error |
| 单元测试 | pytest tests/unit/ | 100% pass |
| 覆盖率 | --cov-fail-under=80 | ≥80% |
| 构建检查 | python -m build | 成功（库项目） |

### 4.2 行为评估（Eval Gate）

对于 Agent 类产品或包含 LLM 调用的代码，必须跑 eval：

```sh
poetry run pytest tests/eval/ -v
```

评估维度与阈值：

| 维度 | 阈值 | 说明 |
|------|------|------|
| 完成率 | ≥95% | 基于 Golden Dataset |
| Rubric 评分 | ≥4.0/5.0 | 质量评分 |
| P95 延迟 | ≤3s | 响应速度 |
| Token 成本 | ≤基线×1.1 | 防止 prompt 膨胀 |
| 幻觉率 | ≤2% | 事实错误比例 |
| 越权次数 | 0 | 安全红线 |
| 回归对比 | ≥-3% | 不能显著退步 |

运行规则：跑 3 轮取中位数，结果写入 eval-report.json。

### 4.3 安全扫描

```sh
poetry run bandit -r src/ -f json -o security-report.json  # Python 安全扫描
poetry run safety check                                     # 依赖漏洞检查
trufflehog filesystem .                                     # 密钥泄露检查
```

| 检查项 | 工具 | 通过条件 |
|--------|------|----------|
| 安全漏洞扫描 | bandit | 零高危，零中危 |
| 依赖漏洞 | safety check | 零高危 |
| 密钥泄露 | trufflehog | 零发现 |
| 硬编码检测 | detect-secrets | 零发现 |

### 4.4 自修复规则

- 失败后最多自修复 3 次
- 每次修复必须记录原因
- 第 4 次失败 → 停止提交，标记为"需人工接管"

## 五、PR 提交规范

### 5.1 自动开 PR

所有门禁通过后，自动创建 Pull Request。

### 5.2 PR 标题

```
[Agent] {类型}: {简要描述}

类型: feat / fix / refactor / test / docs / chore
示例: [Agent] feat: 增加速率限制中间件
```

### 5.3 PR 描述（强制模板）

```markdown
## 📋 变更摘要

- 关联 Issue: {issue_id}
- 改动文件: {文件列表}
- 变更类型: {feat/fix/refactor/test/docs/chore}

## 🧪 测试证据

### 确定性测试

- Black: ✅ 零差异
- isort: ✅ 零差异
- Flake8: ✅ 0 error, 0 warning
- Mypy: ✅ 0 error
- Unit Test: ✅ {通过数}/{总数} pass, 覆盖率 {百分比}%
- Integration Test: ✅ {通过数}/{总数} pass

### Eval 报告

| 维度 | 本次 | 基线 | 变化 |
|------|------|------|------|
| 完成率 | {value} | {baseline} | {delta} |
| Rubric 评分 | {value} | {baseline} | {delta} |
| P95 延迟 | {value} | {baseline} | {delta} |
| Token 成本 | {value} | {baseline} | {delta} |
| 幻觉率 | {value} | {baseline} | {delta} |

### 安全扫描

- Bandit: ✅ 0 高危, 0 中危
- Safety: ✅ 0 高危依赖
- 密钥泄露: ✅ 0

## ⚠️ 风险说明

- {已知风险列表}
- {需要人工确认的事项}

## ✅ 待办

- [ ] {Reviewer 需要确认的内容}
```

### 5.4 禁止提交的情形

- ❌ 缺少 eval 报告
- ❌ 覆盖率低于 80%
- ❌ 安全扫描有高危发现
- ❌ 没有关联 Issue
- ❌ 包含调试代码（print()、TODO 遗留）
- ❌ 单文件超过 300 行且未拆分 commit
- ❌ 提交了 __pycache__、.pyc、venv、.env 等不应提交的文件

## 六、Code Review 配合

### 6.1 自动 Review 响应

当 Reviewer 提出修改意见时：

1. 理解意见并确认修改范围
2. 执行修改后重新跑全部门禁
3. 在评论中回复修改内容和测试结果

### 6.2 需要暂停等待人工确认的场景

遇到以下情况，停止自动操作，等待人工确认：

- Reviewer 标记了 "blocking"
- 涉及金钱计算、权限修改、对外发送
- 数据库 Schema 变更（Django migration / Alembic revision）
- 修改 Prompt 模板 / 修改 Agent 行为逻辑
- 修改 pyproject.toml 中的核心依赖版本
- 修改 CI/CD 配置文件

## 七、合并与后续

### 7.1 合并前

- 确认所有 conversation 已 resolved
- 确认至少 1 人 approve
- 确认 CI 最后一次运行全部通过

### 7.2 合并后

- 删除本地和远程 feature 分支
- 不需要额外操作，CI/CD 会自动处理部署

### 7.3 回滚须知

如果收到回滚指令：

1. 找到上一个稳定版本的 tag
2. 执行 git revert 或 git reset
3. 通知团队

## 八、违规后果

| 违规行为 | 后果 |
|----------|------|
| 跳过 eval 门禁 | 回滚 + 违规计数 +1 |
| 不写测试就提交 | PR 打回 + 违规计数 +1 |
| 覆盖率不达标 | 标记为技术债务 + 违规计数 +1 |
| 安全扫描未过就提交 | 立即回滚 + 安全复盘 |
| 连续 3 次自修复失败仍提交 | Agent 降级为只读模式 |
| 提交 __pycache__/.env 等文件 | 违规计数 +1，强制清理 |
| 累计违规 3 次 | 暂停 Agent 提交权限，人工审核后恢复 |

## 九、快速参考

### 常用命令

```sh
# 一键门禁检查（推荐）
poetry run pre-submit

# 单独检查
poetry run black --check src/ tests/
poetry run isort --check-only src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
poetry run pytest tests/unit/ --cov=src/ --cov-fail-under=80 -v
poetry run pytest tests/integration/ -v
poetry run pytest tests/eval/ -v
poetry run bandit -r src/
poetry run safety check

# 自动修复
poetry run black src/ tests/
poetry run isort src/ tests/

# 构建
poetry build
```

### 目录结构约定

```
src/
  {package_name}/     # 源码包
    __init__.py
    main.py
    ...
tests/
  unit/               # 单元测试
    conftest.py
    test_*.py
  integration/        # 集成测试
    conftest.py
    test_*.py
  eval/               # 行为评估
    conftest.py
    test_*.py
    datasets/         # Golden Dataset
  fixtures/           # 测试数据
    sample_data.json
    mock_responses.yaml
docs/                 # 文档
scripts/              # 工具脚本
  pre-submit.sh       # 预提交脚本
.gitignore            # 必须包含 __pycache__/, *.pyc, .venv/, .env
pyproject.toml        # 项目配置
poetry.lock           # 依赖锁定文件
README.md
AGENTS.md             # 本文件
```

### .gitignore 必备条目

```
# Python
__pycache__/
*.py[cod]
*.so
.Python
*.egg-info/
dist/
build/

# 虚拟环境
.venv/
venv/
env/

# IDE
.vscode/
.idea/

# 环境变量
.env
.env.local

# OS
.DS_Store
Thumbs.db

# 测试产物
.coverage
htmlcov/
.pytest_cache/
```

### Python 工具版本要求

| 工具 | 最低版本 | 安装方式 |
|------|----------|----------|
| Python | 3.10+ | 系统安装 |
| Poetry | 1.5+ | pip install poetry |
| Black | 23.0+ | poetry add --dev black |
| isort | 5.12+ | poetry add --dev isort |
| Flake8 | 6.0+ | poetry add --dev flake8 |
| Mypy | 1.0+ | poetry add --dev mypy |
| Pytest | 7.0+ | poetry add --dev pytest |
| Pytest-cov | 4.0+ | poetry add --dev pytest-cov |
| Pytest-asyncio | 0.21+ | poetry add --dev pytest-asyncio |
| Bandit | 1.7+ | poetry add --dev bandit |
| Safety | 2.0+ | poetry add --dev safety |

---

最后更新：2026-08-14

本文件由 AI 工程化团队维护。如需修改，请创建 Issue 并经过团队 review 后由人工修改。Agent 不得自行修改本文件。

# AGENTS.md —— Python Agent Harness 框架开发规范

> 本文档是**任意 AI Agent（含未来的编码 Agent）在本仓库开发时必须遵循的强制规范**，
> 覆盖目录、命名、代码风格、harness 集成、工具开发、强制代码审查与强制测试。
> **任何一次代码修改或功能新增，必须自动执行对应的服务测试，全部通过才算完成；未经审查与测试验证的代码禁止合入。**

---

## 0. 强制质量门禁（最高优先级，凌驾于一切功能开发之上）

> 本仓库采用「**改码必审、审完必测、测过才交**」的强制工作流。以下两条是硬性门禁，
> 任何 Agent（含本 Agent）在**每次修改代码或增加功能后**，必须自动执行，不得以任何理由跳过或推迟：

### 0.1 强制测试（修改后必须自动运行）

每次代码修改 / 功能新增完成后，**必须立即自动启动对应服务的测试**，直到全部通过：

| 改动范围 | 必须运行的验证命令（Windows PowerShell 下亦适用） |
|---------|--------------------------------------------------|
| 后端任意代码 | `cd src/backend && python -m app.scripts.run_checks`（一键运行 ruff + pytest） |
| 后端静态检查 | `cd src/backend && ruff check .` |
| 后端单元测试 | `cd src/backend && pytest -q` |
| 用户端前端 | `cd src/frontend/web && pnpm run build`（含 vue-tsc 类型检查） |
| 管理端前端 | `cd src/frontend/admin && pnpm run build` |
| 平台端前端 | `cd src/frontend/platform && pnpm run build` |
| 涉及新增/修改接口 | 在上述基础上，必须启动后端服务并以 `curl`/HTTP 客户端验证相关接口响应符合 SSE 事件契约 |

**执行规则（强制）：**
1. 改动后端 → 必须运行 `run_checks`（或 `ruff check .` + `pytest -q` 二者皆跑）。
2. 改动前端某个端 → 必须运行该端的 `pnpm run build`。
3. 测试失败 → 必须立即修复代码并**重新运行测试**，形成「改 → 测 → 改 → 测」循环，直至全绿。
4. 依赖缺失导致无法运行测试时，必须先补齐依赖（`pip install -r requirements.txt` / `pnpm install`）再运行，禁止以「未装依赖」为由跳过测试。
5. 涉及接口/SSE 契约变更时，不得仅靠单元测试通过就结束，还需启动服务做端到端验证（可用 Mock 模型走通完整链路）。

### 0.2 强制代码审查（合入前必须自审）

在完成测试后、宣告任务完成前，必须对照第 9 章审查清单逐项自审；发现违规立即修复并重测。**不允许在审查清单存在未勾选项时提交/交付。**

---

## 1. 项目概述

- **定位**：企业通用 AI Agent 框架，核心是自研的 **harness 运行时**（基于 LangChain/LangGraph）。
- **技术栈**：Python 3.10 + FastAPI + SQLAlchemy 2.0(async) + MySQL 8 + LangGraph + Vue3 前端。
- **三端前端**：`src/frontend/web`（用户端）、`src/frontend/admin`（管理端）、`src/frontend/platform`（平台端）。
- **harness 概念**：Agent = LLM（Provider 抽象）+ 工具（自动注册）+ LangGraph ReAct 循环 + 会话记忆 + SSE 流式。业务通过 harness 组装 Agent，不直接拼 Prompt。

---

## 2. 命名与版权红线（最高优先级）

### 2.1 禁止出现的字符串

> **严禁在本仓库任何位置出现参考来源第三方项目（及其衍生框架）的品牌名、项目名及一切大小写变体字符串。**

禁止出现在：代码、包名、类名、函数名、变量名、注释、配置文件、数据库表名/库名/字段名、文件与目录名、文档、日志、Commit message。

### 2.2 品牌与命名约定

| 项 | 约定 | 示例 |
|----|------|------|
| 项目名 | `Python Agent Harness` | — |
| 后端包名 | `app` | `app.harness` |
| 数据库名 | `redfox_ai` | — |
| 表前缀 | `sys_`（系统）/ `ai_`（AI）/ `sd_`（短剧 shortdrama） | `ai_agent`、`sd_storyboard` |
| 前端目录 | `web` / `admin` / `platform` | — |

### 2.3 通用命名规范

- Python：模块/函数/变量用 `snake_case`，类用 `PascalCase`，常量 `UPPER_SNAKE_CASE`。
- 工具名：`snake_case`，语义化（如 `check_https_certificates`）。
- 表名/字段名：`snake_case`，布尔用 `is_xxx`，状态用 `status`（0 正常 / 1 停用）。
- 前端：组件 `PascalCase`，目录/文件名 `kebab-case` 或 `camelCase` 保持一致。

### 2.4 MIT 开源协议声明（强制）

本项目遵循 **MIT 协议**开源。**所有自研代码文件**（后端 `.py`、前端 `.ts`/`.vue` 等源文件）**必须**在文件头部包含 MIT 协议声明。

**适用范围（必须添加）：**
- 后端 `src/backend` 下所有自研 `.py` 文件（含 `tests/`、`alembic/` 的 env.py、`app/` 全目录）。

**不适用（禁止添加）：**
- 第三方代码 / 依赖包：`node_modules/`、`.venv/`、`site-packages/`、`vite.config.d.ts` 等**构建产物**。
- 第三方静态资源：`app/static/swagger-ui/`、`app/static/redoc/`（上游开源库，保留其自身版权）。
- 空文件（0 字节）、纯配置类文件（`.json`/`.toml`/`.yaml`/`.ini`/`.env*`）。

**声明格式：**

> **作者信息**：版权行作者使用**当前 git 提交用户信息**（`git config user.name` / `user.email`），
> 格式为 `Copyright (c) <年份> <name> <email>`。查询命令：`git config user.name && git config user.email`。
> 本仓库当前作者为 `redfox <591006133@qq.com>`。

Python（`.py`，置于文件第一行，`#` 注释块，其后保留原 docstring/import）：
```python
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
```

TypeScript（`.ts`，置于文件第一行，块注释）：
```ts
/*
 * Copyright (c) 2026 redfox <591006133@qq.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * ...（同上 MIT 全文，行首为 " * "）...
 * SOFTWARE.
 */
```

**强制检查项（新增/修改文件时）：**
- [ ] 新建自研 `.py` / `.ts` 文件必须附带上述 MIT 头部声明。
- [ ] 新增代码不得移除/篡改已有文件的版权声明。
- [ ] 版权年份使用首次创建年份（当前 `2026`），不随修改滚动。
- [ ] 全仓 grep 校验：`Permission is hereby granted` 应出现在所有自研源文件（空文件/第三方除外）。

---

## 3. 后端目录结构与职责

```
src/backend/
├── main.py                    # 入口：路由装配、中间件、lifespan（工具自动发现）
├── app/
│   ├── core/                  # 配置(config)/日志(logger)/异常(exceptions)/安全(security,JWT)/依赖(deps)
│   ├── database/              # async engine、session、Base、BaseEntity、BaseRepository、transaction(统一事务)
│   ├── models/                # SQLAlchemy ORM（system/ai/shortdrama，继承 BaseEntity）
│   ├── repositories/          # ★ 数仓层：每个业务域一个 repository（继承 BaseRepository）
│   ├── schemas/               # Pydantic DTO（输入/输出分离）
│   ├── api/v1/                # 路由层（system/ai/shortdrama）
│   ├── services/              # 业务服务层（编排 harness + 组装数仓）
│   ├── common/                # 统一响应(response)/通用类型(types:Int64)/雪花ID(snowflake)
│   └── harness/               # ★ 可复用 Agent 运行时内核
│       ├── llm/               #   Provider 抽象 + 工厂 + Mock
│       ├── tools/             #   BaseTool + ToolRegistry + builtin/
│       ├── graph/             #   ReActAgent(ReAct循环) + StagePipeline(多阶段流水线)
│       ├── memory/            #   会话记忆
│       ├── schema/            #   结构化输出模型
│       └── stream/            #   SSE 事件封装
└── tests/                     # 单元测试
```

### 分层约束

1. **Controller（api/v1）禁止直接操作 ORM 或调用 harness**，必须经由 `services/`。
2. **services/** 是业务编排层，负责组装 harness（模型 + 工具 + 系统提示词）与数仓，禁止直接编写 SQL / ORM 查询。
3. **repositories/** 是数仓层（数据访问层），**唯一允许操作 ORM 的业务包**；每个表/业务域对应一个 repository，继承 `BaseRepository`。
4. **harness/** 是纯运行时内核，**不得依赖业务 ORM / 业务 schema**（保持可复用、可移植）。
5. 所有 DB 操作用异步（`async/await` + `AsyncSession`）。
6. **Controller / services / repositories 一律不得在业务代码中 `commit`/`rollback`**，事务统一由数仓装饰器与 `transaction()` 管理（见第 7.2 节）。

---

## 4. harness 集成方式

### 4.1 组装一个 Agent（对话场景）

```python
from app.harness.llm import LLMConfig, create_chat_model
from app.harness.graph import ReActAgent
from app.harness.tools import tool_registry

model = create_chat_model(LLMConfig(provider="mock", model_name="mock-chat"))
tools = tool_registry.all_langchain_tools()          # 全部内置工具
agent = ReActAgent(model=model, tools=tools, system_prompt="...")

async for event in agent.stream(messages):            # 产出统一事件
    # event: {"type": "content"|"tool_call"|"tool_result"|"done"|"error", "data": ...}
```

### 4.2 组装多阶段流水线（短剧场景）

```python
from app.harness.graph.pipeline import StagePipeline, PipelineStage

class OutlineStage(PipelineStage):
    name = "outline"
    async def run(self, ctx): ...   # 返回 dict，合并进 ctx

pipeline = StagePipeline([OutlineStage(), EpisodesStage(), StoryboardsStage()])
async for event in pipeline.run({"idea": "..."}):
    # event: {"type": "stage", "data": {"stage":..., "status": "start"|"done", "result":...}}
```

### 4.3 SSE 事件契约（前端对接标准）

| 事件类型 | 说明 | data 结构 |
|---------|------|-----------|
| `content` | 流式文本增量 | `str` |
| `tool_call` | 工具调用请求 | `{name, args, id}` |
| `tool_result` | 工具执行结果 | `{name, content}` |
| `stage` | 流水线阶段进度 | `{stage, status, result?}` |
| `done` | 完成 | 任意 |
| `error` | 错误 | `str` |

> 新增事件类型必须同步更新 `harness/stream/events.py` 的文档与三端前端解析逻辑。

---

## 5. 工具开发规范（新增内置工具）

1. 在 `app/harness/tools/builtin/` 新建模块，继承 `BaseTool`。
2. 必须声明 `name`（snake_case）、`description`（供 LLM 理解用途，写清入参含义）、`args_schema`（Pydantic 模型）。
3. 实现 `async def execute(self, **kwargs) -> Any`，返回**可 JSON 序列化**结果。
4. 工具启动时被 `ToolRegistry.auto_discover()` 自动注册，**无需手写注册代码**。

```python
class MyToolArgs(BaseModel):
    query: str = Field(..., description="查询关键词")

class MyTool(BaseTool):
    name = "my_tool"
    description = "根据关键词做某事"
    args_schema = MyToolArgs

    async def execute(self, **kwargs):
        return {"ok": True}
```

### 工具开发红线

- 工具必须**幂等**、**有超时**、**异常可捕获**（单条失败不拖垮批量）。
- 禁止在工具内直接写库 / 返回 SQLAlchemy 对象 / 返回不可 JSON 序列化对象。
- 涉及外部网络必须 `asyncio` + 超时（默认 5s）。

---

## 6. 新增模型 Provider

1. 在 `harness/llm/factory.py` 的 `create_chat_model` 增加 provider 分支。
2. 返回 LangChain `BaseChatModel` 实例，保证支持 `invoke`/`astream`/`bind_tools`。
3. Mock provider 用于无密钥本地验证，行为必须**确定性、可预期**（禁止随机输出导致测试不稳定）。

---

## 7. 新增业务模块（对齐参考项目分层思想，自研实现）

按「model / schema / repository / service / api」五层新增：

1. `models/xxx.py`：定义 ORM（继承 `app.database.base.BaseEntity`，自动获得雪花 id + 审计字段 + 逻辑删除）。
2. `schemas/xxx.py`：定义 `XxxCreate` / `XxxUpdate` / `XxxOut`（输入输出分离；ID 字段用 `app.common.types.Int64`，保证雪花 ID 序列化为字符串）。
3. `repositories/xxx_repository.py`：定义数仓，继承 `BaseRepository[XxxModel]`，声明 `model_class`，补充领域查询方法。
4. `services/xxx_service.py`：业务编排，注入数仓实例，禁止直接操作 ORM。
5. `api/v1/xxx/xxx.py`：定义 `router`（`APIRouter`），并在 `api/v1/router.py` 注册。
6. 需要新表时用 `alembic revision --autogenerate` 生成迁移，或补充到 `app/scripts/init_db.py`。

### 7.2 数仓层与事务规范（强制）

数仓层是**唯一允许操作 ORM 的业务包**，所有写操作通过 `BaseRepository` 完成。
事务语义由 `app/database/transaction.py` 统一管理，业务代码**禁止手动 `commit`/`rollback`**。

**事务两条规则：**

1. **数仓写方法加 `@auto_commit` 装饰器**（`BaseRepository.create/update/delete` 已内置）：
   - 调用方**不在**统一事务中 → 方法成功后自动 `commit`，异常自动 `rollback`；
   - 调用方**处于** `transaction()` 事务中 → 不提交，交由外层统一处理。
2. **跨数仓/多表写入用统一事务 `transaction()`**：
   - 成功全部自动提交，任一异常整体回滚。

```python
# 规则 1：单次写自动提交（装饰器内置）
await model_repo.create(db, name="qwen", provider_code="dashscope")  # 自动 commit/rollback

# 规则 2：多表原子写入（统一事务）
async with transaction(db) as tx:            # 复用请求级会话；不传则新建独立会话
    project = await project_repo.create(tx, **p)
    script = await script_repo.create(tx, project_id=project.id, **s)
# 退出时全部成功自动 commit；任一步异常自动 rollback（无需手动处理）

# 只读查询不使用装饰器，也不触发提交：
model = await model_repo.get_by_name(db, "qwen")
```

**强制检查项：**
- 新写方法必须加 `@auto_commit`（`from app.database.transaction import auto_commit`）。
- 数仓方法签名第一个参数必须是 `session: AsyncSession`（或命名 `db`），供装饰器定位会话。
- 禁止在 service / controller 中出现 `db.add` / `db.commit` / `db.rollback` / `db.flush` / 裸 `select(...)`。
- 流式场景（如对话）如需逐条持久化，使用单写自动提交；批量原子落库必须走 `transaction()`。
- 数仓只做数据访问，不做业务判断（如权限、校验），业务规则留在 service。

---

## 8. 代码风格

- Python：遵循 PEP 8，行宽 120；用 `ruff` 检查（`ruff check .`），`ruff format` 格式化。
- 类型注解：所有函数签名标注参数与返回类型（`from __future__ import annotations`）。
- 日志：统一用 `app.core.logger.logger`；**禁止打印敏感信息**（api_key 脱敏为 `前4位****后4位`）。
- 异常：业务异常抛 `app.core.exceptions.AppError` 子类，由全局处理器统一转统一响应。
- 前端：TypeScript + `<script setup lang="ts">` + Element Plus；颜色/间距用 CSS 变量（`style.css` 中的设计 token），**禁止硬编码 hex 值到组件**。
- **图标**：使用 `@element-plus/icons-vue` SVG 图标，**禁止用 emoji 充当结构图标**。

---

## 9. 强制代码审查（Mandatory Code Review）

**每次修改代码或增加功能后，必须在本轮任务结束前完成强制自审**，逐项确认；存在未勾选项即视为任务未完成，必须先修复再重测。

### 自审流程（强制）

1. 列出本次改动涉及的全部文件与功能点。
2. 对照下方清单逐项勾选；不适用项标注「N/A」并说明原因。
3. 发现任何违规 → 立即修复 → 按第 0.1 节重新运行对应服务测试 → 回到步骤 2，直至全绿。
4. 最终将审查结果摘要写入交付说明（勾选项 + 测试通过情况）。

### 后端
- [ ] 无任何参考来源第三方项目名称字符串（全仓 grep）。
- [ ] 自研 `.py` 文件头部包含 MIT 协议声明（空文件/第三方/构建产物除外）。
- [ ] Controller 未直接操作 ORM / harness。
- [ ] service 未直接操作 ORM（无 `db.add` / `db.commit` / `db.rollback` / 裸 `select`）；数据访问全部走数仓层。
- [ ] 数仓写方法带 `@auto_commit`；多表写入使用 `transaction()` 统一事务（无手动 commit/rollback）。
- [ ] DB 操作为异步；事务正确（成功 `commit`，异常 `rollback`，由装饰器/事务上下文保证）。
- [ ] 工具幂等、有超时、异常可控、返回可 JSON 序列化。
- [ ] 敏感信息（api_key）未出现在日志 / 响应体明文。
- [ ] 新增路由已注册；Pydantic 输入有校验。
- [ ] 通过 `ruff check`（`python -m app.scripts.run_checks`），无新增 lint/类型错误。
- [ ] 已运行 `pytest`，**本次改动相关测试与全量测试全部通过**。
- [ ] 涉及接口/SSE 契约变更 → 已启动服务做端到端验证（含 `error`/断开场景）。

### 前端
- [ ] 无 emoji 图标；图标来自统一图标库。
- [ ] 自研 `.ts`/`.vue` 文件头部包含 MIT 协议声明（构建产物 `*.d.ts` 除外）。
- [ ] 颜色/间距使用设计 token，无 ad-hoc 硬编码。
- [ ] 表单有 label、校验与错误提示；按钮有 loading/禁用态。
- [ ] SSE 流式处理了 `error` / 断开（AbortController）场景。
- [ ] 交互反馈在 150-300ms；可点击元素 ≥ 44px 命中区。
- [ ] 已运行对应端 `pnpm run build`（含 vue-tsc 类型检查），构建通过。

---

## 10. 测试与验收标准

### 10.1 单元测试要求

- 位置：`src/backend/tests/`，用 `pytest` + `pytest-asyncio`。
- 覆盖重点：工具纯逻辑（域名清洗、证书时间解析）、工具注册表、Mock 模型确定性、密码哈希/JWT。
- 运行：`cd src/backend && pytest`（需先装依赖）。
- **强制**：新增/修改后端代码后，必须补充或更新对应单元测试，且通过 `python -m app.scripts.run_checks` 一键验证（ruff + pytest 全绿）。

### 10.2 测试自动执行（改码必测）

- 任何 Agent 在修改代码或增加功能后，**必须自动启动对应服务的测试**（命令见第 0.1 节表格），不得遗漏。
- 后端全量门禁：`cd src/backend && python -m app.scripts.run_checks`。
- 前端构建门禁：改动哪个端就跑哪个端的 `pnpm run build`。
- 测试失败必须修复重跑，直至全部通过；测试全绿是宣布任务完成的**前置条件**。

### 10.3 MVP1 验收（站群证书检查）

1. 启动后端 + 用户端，登录（`admin / admin123`）。
2. 用户端输入「检查 example.com 和 api.example.com 的 HTTPS 证书过期时间」。
3. 预期：界面出现「检查 HTTPS 证书」工具胶囊 → 工具返回每张证书的 `not_after` / `days_left` / 是否过期 → 流式输出最终回答。
4. 无真实 LLM Key 时，用 Mock 模型（默认）同样走通「LLM → tool_call → 工具执行 → 结果」完整循环。

### 10.4 MVP2 验收（短剧创作流水线）

1. 启动平台端，登录后输入一句短剧创意。
2. 预期：进度条依次点亮「大纲 → 分集 → 分镜」，逐阶段推送结果；最终展示大纲卡片、分集梗概列表、每集分镜提示词卡片（含画面提示词、景别、运镜标签）。
3. 数据库 `sd_project` / `sd_script` / `sd_episode` / `sd_storyboard` 有对应记录。

---

## 11. 快速启动

```bash
# 后端
cd src/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # 按需修改 DB 连接
python -m app.scripts.init_db                        # 建表 + 种子数据(admin/admin123)
uvicorn main:app --host 0.0.0.0 --port 58001 --reload

# 前端（三个端各自独立）
cd src/frontend/web && pnpm install && pnpm run dev      # 用户端 http://localhost:58010
cd src/frontend/admin && pnpm install && pnpm run dev    # 管理端 http://localhost:58011
cd src/frontend/platform && pnpm install && pnpm run dev # 平台端 http://localhost:58012
```
