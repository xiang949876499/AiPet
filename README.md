# 宠物店 AI 复购提醒助手

宠物店 AI 复购提醒助手是一个面向宠物门店的轻量级私域运营工具。第一版聚焦一个问题：店员每天应该联系哪些客户、为什么联系、微信该怎么说。

## 功能

- 客户、宠物、服务记录管理
- 洗护到期与沉睡客户复购提醒
- 试用装回访任务生成
- AI/模板话术生成，支持无 API Key 离线运行
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

## 企业微信内部通知

配置 `.env`：

```env
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_APP_SECRET=
WECOM_INTERNAL_NOTIFY_ENABLED=false
```

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
