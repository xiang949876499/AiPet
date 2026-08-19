# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

宠物店 AI 运营 Agent — 面向社区单店宠物店老板的轻量级私域运营工具。核心场景：客户复购提醒、自媒体内容生成、经营问答、试用装回访、企业微信内部通知。

## 常用命令

```powershell
# 环境与依赖
uv sync                                          # 安装 Python 依赖
cd frontend && npm install && npm run build && cd ..  # 构建 Vue 前端

# 数据库
uv run python main.py init-db                    # 初始化 SQLite 数据库
uv run python main.py seed                       # 导入演示数据
uv run python main.py seed --refresh             # 重建内置豆豆宠物店演示数据

# 启动 Web（开发）
uv run uvicorn web.app:app --reload              # API + 页面，单端口
.\start.ps1                                      # 一键启动（同步依赖→建库→种子→构建前端→启动）

# 测试
uv run pytest tests -q                           # 运行全部测试
uv run pytest tests/test_agents/test_reminder.py -q  # 单文件

# CLI 操作
uv run python main.py reminders pending          # 生成并查看待跟进任务
uv run python main.py customers import-csv --path customers.csv  # CSV 导入客户
uv run python main.py content generate           # 生成今日内容
uv run python main.py content calendar           # 查看内容日历
uv run python main.py ops plan-7-days            # 7 天运营计划
uv run python main.py push send-internal --dry-run  # 企业微信内部推送（试运行）
uv run python main.py outreach scan              # 扫描客户机会生成触达任务
uv run python main.py analytics dashboard        # 经营分析看板
uv run python main.py trial                      # 开启 14 天试用
uv run python main.py license status             # 查看 license 状态
```

## 技术栈

- **Python 3.11+**, 包管理用 `uv`，依赖见 `pyproject.toml`
- **FastAPI** + **Jinja2** 模板 + **Vue 3 + Vite** 前端（构建后由 FastAPI 托管静态文件）
- **SQLAlchemy 2.0** ORM，默认 **SQLite**（`data/pet_agent.db`），可迁移到 PostgreSQL
- **Click + Rich** CLI（`main.py`）
- **OpenAI-compatible** LLM 客户端（`core/llm.py`），支持本地模型（Ollama/LM Studio/llama.cpp）
- **企业微信** 内部通知与 OAuth 登录（`core/wecom_client.py`）
- **pytest**，测试用内存 SQLite

## 架构分层

```
main.py              Click CLI 入口，所有命令在此注册
web/app.py           FastAPI 应用，注册路由、中间件、静态文件
web/routes/          按功能拆分的路由模块（customers, reminders, appointments, advisor, samples, workbench）
agents/              "Agent" 模式 — 每个 agent 封装一类业务逻辑，接收 Session + LLMClient，返回 dict
  base.py            BaseAgent 基类：render_or_fallback 模式（LLM 生成失败时回退模板话术）
  reminder.py        洗护到期提醒生成
  content.py         自媒体内容生成
  growth.py          经营问答(AdvisorAgent)、门店体检(StoreAuditAgent)、周报(WeeklyReportAgent)
  review.py          AI 点评回复
  scheduler.py       定时任务调度
outreach/            客户触达引擎（Phase 1 核心模块）
  rules.py           10 条默认触达规则 + 扫描函数（洗护到期/沉睡唤醒/试用回访/疫苗/驱虫/生日/节日/复购/售后/会员升级）
  engine.py          dispatch_outreach：规则扫描 → DND/频率检查 → 生成 FollowTask + OutreachLog
  confirm_flow.py    触达消息确认/驳回流程
  content_auditor.py 敏感词审核
content_engine/      内容营销引擎
  calendar.py        7 天内容日历构建
  generator.py       模板变量填充 + AI 优化
  templates/         YAML 模板（朋友圈/小红书/抖音各 5 个）
licensing/           License 系统（14 天试用、离线宽限期、降级模式）
  storage.py         本地 license 文件读写，原子写入
  middleware.py      FastAPI 中间件，拦截未激活请求
  client.py          远程 license 服务器通信
services/            业务服务层
  customer_import.py CSV 导入（按手机号幂等更新）
  subscriptions.py   套餐管理
  credits.py         AI Credit 消耗
  ops_dashboard.py   运营看板数据聚合
  weekly_plan.py     7 天运营计划
  wecom_push.py      企业微信消息发送
analytics/           数据分析（回复率、转化率、归因收入）
core/                基础设施
  llm.py             LLMClient：OpenAI-compatible 接口封装，支持多 provider、超时、自动回退
  wecom_client.py    企业微信 API 客户端
  scheduler.py       任务调度
  push_policy.py     推送策略
  prompt_templates.py 提示词模板
app/                 数据层
  config.py          Pydantic Settings，从 .env 加载
  models.py          全部 SQLAlchemy 模型（Store/Customer/Pet/FollowTask/OutreachLog/ContentItem 等）
  database.py        数据库引擎、SessionLocal、init_db、SQLite schema 自动兼容补丁
  schemas.py         Pydantic schema
```

## 关键设计约定

- **离线优先**：LLM 不可用时自动回退到模板话术，系统核心功能不依赖 API Key
- **Agent 模式**：`agents/` 下的类接收 `Session` + 可选的 `LLMClient`，`execute(context: dict) -> dict` 是统一入口。并非所有 agent 都继承 BaseAgent（如 ReminderAgent 是独立类但遵循相同约定）
- **SQLite schema 迁移**：`database.py` 的 `_ensure_sqlite_schema_compatibility` 通过 `ALTER TABLE ADD COLUMN` 自动补全缺失列，不需要手动 migration
- **License 控制**：`LicenseMiddleware` 拦截请求检查 license 状态；`LicenseStorage` 支持试用 token、付费 token、离线宽限期、降级功能集
- **DND/频率控制**：`outreach/engine.py` 的 `can_dispatch_to_customer` 检查全局免打扰、临时免打扰、渠道/消息类型屏蔽、每日/每月频率上限、套餐日上限
- **Credit 系统**：AI 操作按任务消耗 Credit（点评回复 1、文案生成 5、短视频 3、门店体检 20），耗尽或试用到期停止生成
- **企业微信**：当前仅用于内部成员推送待办提醒（不自动群发外部客户）。外部客户消息需店员手动确认后复制发送
- **合规边界**：不提供宠物医疗问诊/诊断/用药建议；所有客户侧话术由店员确认后手动发送

## 测试约定

- `tests/conftest.py` 提供 `db_session` fixture（内存 SQLite）和 `sample_records` fixture（预置门店/客户/宠物/服务记录）
- 测试文件按模块映射：`tests/test_agents/` ↔ `agents/`，`tests/test_web/` ↔ `web/`
- `pyproject.toml` 中 `pythonpath = ["."]` 确保测试可直接 import 项目模块
