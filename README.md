# AiPet

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="AiPet 宠物店 AI 复购提醒助手：服务记录生成待办，员工审核后再人工联系客户">
</p>

<p align="center">
  <strong>宠物店 AI 复购提醒助手</strong><br>
  Create reviewed follow-up tasks from store records — never automatic customer blasts.
</p>

## 这是什么 / What it is

AiPet 是面向宠物门店的轻量级客户运营工具。它聚焦一个日常问题：店员今天应该联系哪些客户、为什么联系、应该怎样组织话术。

AiPet turns customer, pet, appointment, service, and trial records into follow-up tasks. AI can draft a message, but the staff member remains responsible for review and customer contact.

## 核心能力 / What you can do

- 管理客户、宠物、服务、预约、商品购买与试用相关记录。
- 生成洗护到期、沉睡客户和试用装回访等提醒任务。
- 通过 AI 或本地模板生成可编辑的跟进话术。
- 在 CLI 和 Web 今日工作台处理待办。
- 使用企业微信向门店内部员工发送提醒，并支持 dry-run 与发送状态回写。
- 使用 SQLite 本地运行，并为后续 PostgreSQL 迁移保留数据层。

## 工作流 / How it works

1. 门店维护客户、宠物与服务记录。
2. 提醒 Agent 根据服务周期和客户状态生成待办及触发原因。
3. 系统生成 AI 或模板话术。
4. 企业微信只通知门店内部员工。
5. 店员审核、编辑并手动联系客户。

The automation stops at the staff workflow. Customer-facing messages are never bulk-sent automatically in this MVP.

## 快速开始 / Quick start

项目使用 uv 管理 Python 环境和依赖。

~~~powershell
uv sync
uv run python main.py init-db
uv run python main.py seed
uv run python main.py dashboard
~~~

查看待办：

~~~powershell
uv run python main.py reminders pending
uv run python main.py push list
~~~

启动 Web 工作台：

~~~powershell
uv run uvicorn web.app:app --reload
~~~

打开 / Open:

- 今日工作台 / Dashboard: http://localhost:8000
- 推送任务 / Push tasks: http://localhost:8000/push-tasks

## 企业微信内部提醒 / WeCom internal notifications

在 .env 中配置门店内部应用。测试和演示时优先使用 dry-run。

~~~env
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_APP_SECRET=
WECOM_INTERNAL_NOTIFY_ENABLED=false
~~~

常用操作：

~~~powershell
uv run python main.py push create-internal --follow-task-id 1 --staff-id 1
uv run python main.py push send-internal --dry-run
uv run python main.py push send-internal
~~~

只有 WECOM_INTERNAL_NOTIFY_ENABLED=true 时，send-internal 才会真实调用企业微信。

企业微信登录还需要：

~~~env
WECOM_REDIRECT_URI=https://your-domain/wecom/oauth/callback
WECOM_OAUTH_ENABLED=true
~~~

将回调域名加入企业微信可信域名，并确保应用可见范围包含门店员工。登录入口：

~~~text
http://localhost:8000/wecom/oauth/start
~~~

## 离线模式与合规边界 / Fallback and safety boundaries

没有配置 OPENAI_API_KEY 时，AiPet 使用模板话术继续生成待办，便于本地验证和日常兜底。

本项目不提供宠物健康问诊、疾病诊断、用药建议、治疗建议或医疗图片识别。涉及健康问题时，应建议客户联系专业兽医或正规宠物医院。

All customer-side contact requires staff confirmation and manual sending. WeCom integration is for internal task notification, not automatic external marketing.

## 验证 / Verify

~~~powershell
uv run pytest tests -q
~~~

## 项目结构 / Project map

~~~text
app/        配置、数据库、SQLAlchemy 模型与 Pydantic schema
agents/     ReminderAgent、SchedulerAgent 与 SampleAgent
core/       Prompt 模板、Orchestrator、策略与企业微信客户端
web/        FastAPI + Jinja2 工作台
tests/      单元测试与集成测试
main.py     Click + Rich CLI 入口
seed_data.py 演示数据导入
~~~
