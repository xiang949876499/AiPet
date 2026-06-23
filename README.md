# 宠物店 AI 运营 Agent

宠物店 AI 运营 Agent 是一个面向社区单店宠物店老板的轻量级私域运营工具。它不做完整收银、进销存或硬件管理，而是聚焦一个更直接的问题：老板每天应该维护哪些客户、为什么联系、微信该怎么说、今天该发什么自媒体内容。

## 功能

- 客户、宠物、服务记录管理
- 洗护到期与沉睡客户复购提醒
- 试用装回访任务生成
- AI/模板话术生成，支持无 API Key 离线运行
- 自媒体内容日历，支持朋友圈、小红书、短视频脚本草稿
- 订阅套餐配置，默认主推专业版 ¥499/月
- 7 天运营计划，按客户机会生成每日触达和内容主题
- CSV 客户导入，支持按手机号幂等更新客户和宠物资料
- 试用期状态和 AI 生成额度限制
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
uv run python main.py customers import-csv --path .\customers.csv
uv run python main.py content generate
uv run python main.py content list
uv run python main.py ops plan-7-days
uv run python main.py push list
uv run python main.py push send-internal --dry-run
uv run python main.py trial
uv run python main.py license status
uv run python main.py outreach scan
uv run python main.py outreach confirm-list
uv run python main.py content calendar
uv run python main.py analytics dashboard
```

启动 Web 工作台：

```powershell
.\start.bat
```

开发调试时也可以手动启动：

```powershell
uv run uvicorn web.app:app --reload
```

浏览器打开：

```text
http://localhost:8000
http://localhost:8000/customers
http://localhost:8000/customers/import
http://localhost:8000/appointments
http://localhost:8000/outreach
http://localhost:8000/samples
http://localhost:8000/license
http://localhost:8000/outreach/confirm
http://localhost:8000/content/calendar
http://localhost:8000/review
http://localhost:8000/activity
http://localhost:8000/audit
http://localhost:8000/weekly-report
http://localhost:8000/advisor
http://localhost:8000/settings
http://localhost:8000/settings/rules
http://localhost:8000/admin/monitoring
```

可选开启后台登录和授权守卫：

```env
AIPET_AUTH_ENABLED=true
AIPET_ADMIN_PASSWORD=请改成你的后台密码
AIPET_REQUIRE_LICENSE=true
```

开启后访问工作台会先进入 `/login`；未激活时会进入 `/activate`，可输入激活码或先开启 14 天本机试用。

## Phase 1 Daily Operations Loop

Phase 1 adds the sellable daily loop: import customer data, generate explainable outreach opportunities, review or send scripts after compliance checks, record outcomes, and review attributed business impact on the dashboard.

New local modules:

- `licensing/`: local 14-day growth trial, plan-based offline grace, and downgrade mode.
- `outreach/`: 10 default follow-up rules, decision cards, DND/frequency checks, sensitive-word audit, confirmation flow, and guarded WeCom external sends.
- `content_engine/`: 15 Moments/Xiaohongshu/Douyin templates, variable autofill, editable image prompt fallback, and 7-day content calendar data.
- `analytics/`: reply rate, 7-day visit conversion, attributed revenue, recovered revenue, customer health, and tiered dashboard aggregation.
- `aipet-license/`: FastAPI scaffold for the deployable license validation service.

首页现在是老板视角的 **数据首页**，只展示经营结论和关键变化，包含：

- 当前订阅套餐和本月 Credit 用量
- 预计带回收入、待跟进客户、已发布内容、客户回复率
- 今日经营漏斗和近 7 天趋势
- 关键预警和 AI 数据摘要

统一工作台入口：`/` 首页提供左侧一级导航；生成、接待、内容、点评、报告复盘、店铺设置等功能入口均从左侧导航进入，例如 `/outreach`、`/content/calendar`、`/review`、`/weekly-report`、`/settings`。

Web API：

```text
GET  /api/customers
GET  /api/appointments
GET  /api/reminders?status=pending
POST /api/reminders/{task_id}/send
GET  /api/samples
GET  /
```

后台操作入口：

- `/customers/import` 支持下载 CSV 模板、上传前预检、批量创建或更新客户、宠物和洗护周期信息；导入完成后可一键生成今日提醒。
- `/customers` 支持按全部、待跟进、免打扰、最近到店超期筛选客户，可全选当前页或勾选客户后批量生成企业微信内部提醒、批量标记待跟进已发送；也可进入客户档案页查看客户概览、宠物资料、服务记录、待跟进任务和可复制话术，维护标签、备注和免打扰状态。
- `/outreach` 统一承接复购提醒、客户触达、内部推送确认和执行反馈；旧 `/reminders`、`/push-tasks` 入口会导向统一工作台。
- `/content/calendar` 支持生成今日内容、标记朋友圈/小红书/抖音脚本已发布，并记录点赞、评论、转发和咨询数据。

CSV 导入支持以下常用表头：

```text
客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店
```

重复导入时，系统会优先按门店内手机号匹配客户，并更新微信名、最近到店和宠物洗护周期，避免产生重复客户。上传前可先点“预检文件”，系统只检查行数和常见格式问题，不会写入数据库。带有“最近到店”的宠物记录会同步生成洗护服务记录，供复购提醒规则使用。

## 订阅套餐

内置四档套餐：

| 套餐 | 月付 | 目标客户 | 核心能力 |
|---|---:|---|---|
| 体验版 | ¥19/月 | 想轻量试用的门店 | 100 Credit，点评回复、基础内容生成 |
| 入门版 | ¥199/月 | 刚开始做私域的小店 | 500 Credit，客户提醒、基础话术、手动复制发送、内容草稿 |
| 专业版 | ¥499/月 | 主力社区宠物店 | 1500 Credit，企业微信、内容日历、客户分层、复购追踪、活动方案 |
| 增长版 | ¥999/月 | 重视私域增长的门店 | 3000 Credit，活动 Agent、自媒体批量生成、周报、体检报告 |

演示数据会自动为门店创建专业版试用订阅。

AI 操作按任务消耗 Credit，例如点评回复 1、活动方案 5、短视频脚本 3、门店体检 20、每周复盘 20。Credit 耗尽或试用到期时，系统不会继续生成对应结果。

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
web/        FastAPI + Jinja2 工作台、管理页面、API routes
tests/      单元测试和集成测试
main.py     Click + Rich CLI 入口
seed_data.py 演示数据导入
```

## 离线模式

即使没有配置 `OPENAI_API_KEY`，系统也会使用模板话术生成待跟进任务，保证门店工作台可用。后续接入 LLM API 后，可替换为更自然的个性化话术。
