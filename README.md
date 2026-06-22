# 宠物店 AI 运营 Agent

宠物店 AI 运营 Agent 是一个面向社区单店宠物店老板的轻量级私域运营工具。它不做完整收银、进销存或硬件管理，而是聚焦一个更直接的问题：老板每天应该维护哪些客户、为什么联系、微信该怎么说、今天该发什么自媒体内容。

## 功能

- 客户、宠物、服务记录管理
- 洗护到期与沉睡客户复购提醒
- 试用装回访任务生成
- AI/模板话术生成，支持无 API Key 离线运行
- 自媒体内容日历，支持朋友圈、小红书、短视频脚本草稿
- 订阅套餐配置，默认主推专业版 ¥499/月
- 运营看板：客户机会、触达任务、内容产出、预计挽回营业额
- 企业微信内部应用通知任务，支持 dry-run 和发送状态回写
- CLI 工作台和 Web 今日工作台
- SQLite 本地数据库，后续可迁移到 PostgreSQL

## 合规边界

本项目不提供宠物健康问诊、疾病诊断、用药建议、治疗建议或医疗图片识别。涉及健康、疾病、治疗的问题，应建议客户联系专业兽医或正规宠物医院。

MVP 阶段不自动群发外部客户消息。所有客户侧话术由系统生成后，必须由店员确认并手动复制发送。企业微信能力当前只用于给门店内部成员推送待办提醒。

## 快速开始

本项目使用 uv 管理 Python 环境和依赖。

```powershell
uv sync
uv run python main.py init-db
uv run python main.py seed
uv run python main.py dashboard
uv run python main.py reminders pending
uv run python main.py subscription plans
uv run python main.py content generate
uv run python main.py content list
uv run python main.py push list
uv run python main.py push send-internal --dry-run
```

启动 Web 工作台：

```powershell
uv run uvicorn web.app:app --reload
```

浏览器打开：

```text
http://localhost:8000
http://localhost:8000/push-tasks
```

首页现在是老板视角的 **AI 运营工作台**，包含：

- 当前订阅套餐和剩余 AI 额度
- 今日客户机会和可复制话术
- 今日运营任务
- 今日内容日历
- 本周触达任务、本周内容产出、预计挽回营业额

## 订阅套餐

内置四档套餐：

| 套餐 | 月付 | 目标客户 | 核心能力 |
|---|---:|---|---|
| 入门版 | ¥199/月 | 刚开始做私域的小店 | 客户提醒、基础话术、手动复制发送 |
| 专业版 | ¥499/月 | 主力社区宠物店 | 企业微信、内容日历、客户分层、复购追踪 |
| 增长版 | ¥999/月 | 重视私域增长的门店 | 活动 Agent、自媒体批量生成、月度报告 |
| 代运营包 | ¥1999/月起 | 没时间执行的老板 | 内容规划、活动策划、素材托管 |

演示数据会自动为门店创建专业版试用订阅。

## 企业微信内部通知

配置 `.env`：

```env
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_APP_SECRET=
WECOM_INTERNAL_NOTIFY_ENABLED=false
```

企业微信登录还需要配置：

```env
WECOM_REDIRECT_URI=https://你的域名/wecom/oauth/callback
WECOM_OAUTH_ENABLED=true
```

在企业微信后台把 `WECOM_REDIRECT_URI` 对应域名加入应用可信域名，并确认应用可见范围包含门店店员。登录入口：

```text
http://localhost:8000/wecom/oauth/start
```

登录成功后，系统会用企业微信 `UserID` 绑定本地店员，并写入本地登录 cookie。

常用命令：

```powershell
uv run python main.py push create-internal --follow-task-id 1 --staff-id 1
uv run python main.py push send-internal --dry-run
uv run python main.py push send-internal
```

`send-internal` 只有在 `WECOM_INTERNAL_NOTIFY_ENABLED=true` 时才会真实调用企业微信；测试和演示优先使用 `--dry-run`。

## 测试

```powershell
uv run pytest tests -q
```

## 项目结构

```text
app/        配置、数据库、SQLAlchemy 模型、Pydantic schema
agents/     ReminderAgent、SchedulerAgent、SampleAgent
core/       Prompt 模板与 AgentOrchestrator
web/        FastAPI + Jinja2 工作台
tests/      单元测试和集成测试
main.py     Click + Rich CLI 入口
seed_data.py 演示数据导入
```

## 离线模式

即使没有配置 `OPENAI_API_KEY`，系统也会使用模板话术生成待跟进任务，保证门店工作台可用。后续接入 LLM API 后，可替换为更自然的个性化话术。
