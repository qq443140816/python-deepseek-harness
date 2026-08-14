python-agent-harness
This repository hosts system development and runtime components:
pdsh (python-deepseek-harness): Root directory src/pdsh/ + web/.
A general-purpose Agent harness framework (FastAPI + Vue3). See Part 1 below and docs/PLAN.pdsh.md for details.
Python DeepSeek Harness
An enterprise-developed, general-purpose AI Agent harness framework in Python. Modeled after the general agent core of DeepSeek Harness (dsh), this project is a ground-up reimplementation using Python 3.10 + FastAPI (backend) and Vue 3 + Vite + TypeScript (frontend). It strips away code-specific capabilities while retaining general-purpose agent functionality.
Architecture Overview

Core Principles (aligned with dsh):
Model Visibility ⟺ Persistence: All context entering the model is persisted as session events, enabling full replayability.
Open Tool Registry: Enterprises can integrate private tools (approval workflows, knowledge bases, etc.) via the Tool protocol.
Capability Seam: LLM, storage, and tools are all replaceable abstractions. The default implementation targets the official DeepSeek API (OpenAI-compatible).
Quick Start
sh

Visit http://127.0.0.1:8000 (production) or http://127.0.0.1:5173 (development) in your browser.
Configuration
Environment Variable
Description
Default
PDSH_API_KEY
LLM API Key (required for openai mode; never persisted or logged)
—
PDSH_BASE_URL
OpenAI-compatible API endpoint
https://api.deepseek.com
PDSH_MODEL
Model name
deepseek-chat
PDSH_LLM_PROVIDER
openai (real API) / mock (script playback, keyless development)
openai
PDSH_DB_URL
MySQL connection string
mysql+aiomysql://root:root@127.0.0.1:3306/pdsh
PDSH_WORKSPACE
Root workspace directory for shell/fs tools
./workspace
PDSH_MAX_ITERATIONS
Max agent iterations per turn

PDSH_TOOL_TIMEOUT
Timeout per tool execution (seconds)

PDSH_SNOWFLAKE_WORKER_ID
Snowflake ID worker/machine ID

Entity Specifications
All business tables inherit from BaseEntity (← MinimalEntity):
MinimalEntity: Minimal entity base class containing only a snowflake primary key (BIGINT).
BaseEntity: Adds revision (optimistic locking), created_by / created_time / updated_by / updated_time (audit fields), and is_deleted (soft delete).
Development
Follow AGENTS.md: Plan first, enforce test gates (pytest coverage ≥80%), Mock LLM contract tests, and security scanning.
sh


Architecture & Key Mechanisms: docs/architecture.md
Planning & Decision Records: docs/PLAN.pdsh.md
ACP (Minimal stdio JSON-RPC Subset): python -m pdsh.acp
License
MIT © redfox 591006133@qq.com
This project is an independent Python reimplementation based on the general-purpose capabilities of DeepSeek Harness and has no code-level dependency on the official DeepSeek repository.