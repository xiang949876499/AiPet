# 宠物店 AI 复购提醒助手 Agent 实施计划

## 订阅化运营 Agent 增量（2026-06-22）

已将产品方向从单点复购提醒扩展为“宠物店 AI 运营 Agent”订阅 MVP：

- 新增订阅套餐模型：入门版、专业版、增长版、代运营包，主推专业版 ¥499/月。
- 新增门店订阅状态和 AI 月额度记录。
- 新增自媒体内容日历模型，覆盖朋友圈、小红书、短视频脚本草稿。
- 新增 `ContentAgent`，支持 LLM 生成内容，并在无 API Key 时使用离线兜底文案。
- 新增客户机会与运营指标服务，支持客户分层、建议动作、可复制话术、预计挽回营业额。
- 首页升级为老板视角的 AI 运营工作台。
- CLI 新增 `subscription plans`、`content generate`、`content list`。

验证命令：

```powershell
uv run pytest tests -q
```

> **给 agent 执行者：** 实施本计划时，建议使用 `superpowers:subagent-driven-development`，也可以使用 `superpowers:executing-plans` 按任务逐项执行。步骤使用 checkbox 语法，便于跟踪。工程代码级细节参考同目录下 `2026-06-17-pet-agent-implementation-plan.md`。

**目标：** 做出第一版可交付的宠物门店私域运营 Agent，让店员每天知道「该联系谁、为什么联系、微信该怎么说」，并能记录跟进结果。

**架构：** 第一版采用人工确认闭环：客户/宠物/服务记录进入数据库，规则 Agent 生成待跟进任务，LLM 只负责生成微信话术和试用装回访话术，店员手动复制发送并记录结果。MVP 不做健康问诊、疾病诊断、用药建议、支付、库存和自动群发。

**Tech Stack：** Python 3.11+、uv、FastAPI、SQLAlchemy 2.0、SQLite、APScheduler、Click、Rich、Jinja2、OpenAI SDK。V0.1 可先用飞书多维表格/Airtable + Dify/Coze 快速验证；V0.5 进入 Python Web/CLI MVP。

---

## 一、资料依据与范围决策

已阅读目录下资料：

- `宠物门店 AI 管家设计文档 V1.0.pdf`
- `新建 文本文档.txt`
- `新建 文本文档 (3).txt`
- `宠物门店AI管家 MVP 产品设计文档.docx`
- `docs/superpowers/plans/2026-06-17-pet-agent-implementation-plan.md`

关键冲突：

- PDF 与 V1.0 MVP 文本明确排除宠物健康问诊、疾病诊断、用药建议、医疗建议。
- Word 文档包含「AI 健康轻问诊 / 智能前台」设想。
- 本计划以 PDF、V1.0 MVP 文本和工程计划的安全边界为准：MVP 不做问诊，只在健康相关输入出现时输出保守转接建议，例如联系专业兽医或正规宠物医院。

第一版市场名称：

- 第一版叫 `宠物店 AI 复购提醒助手`，让店主一眼看懂价值。
- 功能扩展到预约排期、试用装、商品复购、私域素材和自动触达后，再升级为 `宠物门店 AI 管家`。

## 二、产品路线与工程路线的关系

本文件是主实施计划，负责确定产品边界、Agent 分工、阶段路线和验收标准。

`2026-06-17-pet-agent-implementation-plan.md` 是工程代码级计划，已经给出 Python 项目结构、17 个开发任务、测试方式和 README 收尾动作。执行开发时以本文件的业务优先级为准，以源工程计划的代码任务为落地模板。

整合原则：

- 先验证业务，再产品化。
- 先人工确认，再自动触达。
- 先复购提醒，再扩展预约、试用装和商品复购。
- 先 SQLite 单店 MVP，再考虑 PostgreSQL、多门店、企业微信和 SaaS 化。

## 三、三种实施路径

### 路径 A：零代码验证版

用飞书多维表格或 Airtable 管理数据，用 Dify/Coze 生成话术，店员人工复制到微信发送。

适合：

- 2-3 天内做出可演示版本。
- 快速验证门店是否愿意使用和付费。
- 在写完整系统前先拿到 3 家种子门店反馈。

代价：

- 权限、体验、数据隔离和产品化能力较弱。

### 路径 B：直接开发 Python Web MVP

按源工程计划实现 FastAPI + SQLite + APScheduler + CLI/Web 双界面。

适合：

- 已经确认需求真实，准备产品化收费。
- 需要更规范的数据模型、Agent 编排、测试和后续扩展。

代价：

- 首次交付更慢，验证成本更高。

### 路径 C：混合路径

先做 V0.1 零代码验证版，再把被验证的流程沉淀为 V0.5 Python Web/CLI MVP。

推荐：

- 采用路径 C。
- 目录资料强调轻量交付、低门槛、人工复制发送、不要先开发完整系统；源工程计划提供了进入 Web MVP 后的完整代码蓝图。两者结合最稳。

## 四、MVP 功能边界

### P0 必须做

- 客户档案。
- 宠物档案。
- 服务记录。
- 复购提醒任务生成。
- 今日待跟进工作台。
- AI 话术生成。
- 跟进状态记录。
- CLI 演示入口。
- Web 工作台首页。
- 演示数据导入。

### P1 第二批做

- 预约排期。
- 试用装 T+1/T+4/T+7 回访。
- 商品复购提醒。
- 基础数据看板。
- 员工权限。
- Web 客户列表、预约列表、提醒列表。

### P2 后续做

- 企业微信。
- 短信提醒。
- 服务号/小程序订阅消息。
- 多门店。
- 私域内容助手。
- 节日营销日历。
- 自动化触达。

### 明确不做

- 健康问诊。
- 疾病诊断。
- 用药建议。
- 宠物医疗图片识别。
- 完整收银系统。
- 库存系统。
- 复杂会员卡系统。
- 未经店员确认的自动群发。

## 五、目标工程架构

源工程计划采用三层模块化结构：

- 交互层：Click + Rich CLI，FastAPI + Jinja2 Web。
- Agent 层：SchedulerAgent、ReminderAgent、SampleAgent，由 AgentOrchestrator 统一调度。
- 数据层：SQLAlchemy ORM + SQLite，后续可迁移到 PostgreSQL。

核心运行链路：

```text
客户/宠物/服务记录
-> 定时任务扫描
-> AgentOrchestrator 调用对应 Agent
-> 规则生成跟进任务
-> LLMClient 生成话术
-> CLI/Web 工作台展示
-> 店员复制微信发送
-> 店员记录结果
-> 数据看板统计转化
```

MVP 降级策略：

- 没有 LLM API Key 时，系统仍能生成规则任务，并用模板话术兜底。
- LLM 请求失败时，返回可编辑的模板文案，不阻塞工作台。
- 定时任务不可用时，可通过 CLI 手动触发扫描。

## 六、工程文件结构

按源工程计划，V0.5 Web/CLI MVP 使用以下结构：

```text
ai-pet-agent/
├── main.py
├── requirements.txt
├── .env.example
├── README.md
├── seed_data.py
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   └── schemas.py
├── agents/
│   ├── __init__.py
│   ├── base.py
│   ├── scheduler.py
│   ├── reminder.py
│   └── sample.py
├── core/
│   ├── __init__.py
│   ├── llm.py
│   ├── prompt_templates.py
│   ├── orchestrator.py
│   └── scheduler.py
├── web/
│   ├── __init__.py
│   ├── app.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── customers.py
│   │   ├── appointments.py
│   │   ├── reminders.py
│   │   └── samples.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── customers.html
│   │   ├── appointments.html
│   │   └── reminders.html
│   └── static/
│       └── style.css
├── cli/
│   ├── __init__.py
│   └── commands.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_models.py
    ├── test_cli.py
    ├── test_integration.py
    ├── test_agents/
    │   ├── test_base.py
    │   ├── test_scheduler.py
    │   ├── test_reminder.py
    │   └── test_sample.py
    └── test_core/
        ├── test_database.py
        ├── test_llm.py
        ├── test_prompt_templates.py
        ├── test_orchestrator.py
        └── test_scheduler_jobs.py
```

## 七、Agent 分工

### 1. Product Scope Agent

职责：

- 把产品资料收敛成 P0/P1/P2。
- 防止健康问诊、自动群发、收银库存等功能提前进入 MVP。

验收：

- P0/P1/P2 与本计划第四节一致。
- 任何新功能必须标注业务价值、实现成本、验证方式。

### 2. Data Model Agent

职责：

- 定义 Agent 判断「该联系谁」所需的最小数据。

P0 数据实体：

- `store`：门店身份、业务类型。
- `staff`：老板、店长、店员角色。
- `customer`：宠主资料、来源、标签、最近到店、累计消费、消费次数。
- `pet`：宠物资料、品种、类型、护理周期、性格标签。
- `service_record`：服务日期、服务类型、金额、员工、下次建议时间。
- `follow_task`：任务类型、优先级、生成原因、建议动作、到期日、状态、AI 话术、跟进结果。

P1 数据实体：

- `appointment`
- `product`
- `product_purchase`
- `sample_trial`

验收：

- 门店可以创建或导入客户、宠物、服务记录。
- 系统不依赖收银、库存或完整 CRM，也能生成跟进任务。
- 只采集服务必要数据，避免过度收集隐私。

### 3. SchedulerAgent

职责：

- 管理预约排期和基础档期校验。
- 在 P0 阶段可先提供离线规则和演示数据；P1 再完善预约冲突与日历。

P0 行为：

- 给演示数据生成今日预约、未来预约和服务完成记录。
- 支持 CLI/Web 查询今日预约。

P1 行为：

- 创建预约。
- 查询每日/每周排期。
- 检查预约时间冲突。
- 服务完成后生成下一次复购机会。

验收：

- 同一员工/同一宠物同一时段不能重复预约。
- 预约完成后能写入服务记录或触发后续提醒。

### 4. ReminderAgent

职责：

- 生成洗护/美容/寄养/沉睡客户复购任务和微信话术。

P0 规则：

- 洗护/美容提醒：宠物上次相关服务超过护理周期，且近期没有同类任务。
- 预流失提醒：超过建议周期 7 天仍未预约。
- 沉睡客户唤醒：60/90 天没有任何服务记录。
- 免打扰抑制：客户标记免打扰，或近期明确拒绝跟进时跳过。

验收：

- 每个任务都包含客户、宠物、任务类型、优先级、原因、建议动作、到期日。
- 原因必须让店员看得懂，例如：`豆豆上次洗护距今 24 天，最近 7 天没有预约`。
- MVP 不自动外发消息。

### 5. SampleAgent

职责：

- 管理试用装回访和转化话术。

P1 规则：

- T+1：询问适口性和食用反应。
- T+4：二次跟进并自然引导正装购买。
- T+7：对未明确拒绝的客户推送优惠或记录偏好。

验收：

- 试用装任务能按领取时间生成。
- 结果可记录为喜欢、一般、不喜欢、未试用、未回复、已成交。
- 低意向客户只记录偏好，不继续高频打扰。

### 6. Prompt 与话术 Agent

职责：

- 管理 Prompt 模板和变量渲染。
- 让 LLM 输出可直接复制到微信的话术。

输入变量：

- 客户称呼。
- 宠物名、类型、品种、性格标签。
- 上次服务类型和时间。
- 提醒原因。
- 可预约时间或门店活动。
- 门店话术风格。

输出：

- 简短版。
- 温和版。
- 促销版。

安全边界：

- 不诊断疾病。
- 不建议用药或治疗。
- 不制造焦虑。
- 不承诺保证复购、销量翻倍、确定营收增长。
- 没有明确活动配置时，不擅自承诺优惠。

验收：

- 每条话术控制在 100-120 个中文字符内。
- 每条话术包含轻柔行动引导。
- 出现健康/疾病/治疗相关输入时，只输出保守转接建议。

### 7. AgentOrchestrator

职责：

- 统一注册和调用 SchedulerAgent、ReminderAgent、SampleAgent。
- 给 CLI、Web、定时任务提供一致入口。

验收：

- `execute(agent_name, context)` 能路由到正确 Agent。
- 未知 Agent 返回明确错误。
- LLM 不可用时不影响规则任务生成。

### 8. QA 与合规 Agent

职责：

- 验证规则、话术、隐私、降级路径和端到端流程。

测试范围：

- 规则测试：洗护周期、60/90 天沉睡、近期预约抑制、免打扰抑制。
- Prompt 测试：长度、语气、多版本、无医疗诊断、无夸大承诺。
- E2E 测试：创建档案、创建服务记录、生成任务、生成话术、标记发送、记录结果、查看指标。
- 隐私审查：授权提示、最小数据采集、门店数据隔离。

验收：

- MVP 不包含健康问诊。
- 未经店员确认，不自动发送外部消息。
- 种子门店数据不能互相泄露。

## 八、阶段计划

### Phase 0：产品切口与演示脚本

周期：

- 0.5-1 天。

任务：

- [ ] 确认 MVP 不做健康问诊、支付、库存、自动群发、多门店。
- [ ] 准备 20-30 条演示数据，覆盖活跃、预流失、沉睡、试用装、商品复购场景。
- [ ] 写第一版演示脚本：`店员打开系统 -> 看到今日待跟进 -> 生成话术 -> 复制微信 -> 记录结果`。

交付物：

- 演示数据集。
- 1 条完整演示路径。

验收命令：

```powershell
Get-ChildItem -LiteralPath "D:\zx\AIPet\docs\superpowers\plans"
```

### Phase 1：V0.1 零代码验证 Agent

周期：

- 2-3 天。

任务：

- [ ] 建飞书多维表格/Airtable：客户、宠物、服务记录、跟进任务。
- [ ] 用公式或筛选视图生成到期客户、60/90 天沉睡客户。
- [ ] 用 Dify/Coze 搭建洗护提醒、沉睡唤醒两条话术生成工作流。
- [ ] 给跟进任务加状态：待处理、已发送、已回复、已预约、已拒绝、已跳过。
- [ ] 用演示数据跑内部测试。
- [ ] 录制 1 分钟演示视频，用于寻找种子门店。

交付物：

- 可生成今日跟进清单和微信话术的演示版。

验收标准：

- 店员能在 10 秒内看到今天要联系的客户。
- 每个待办都有明确原因和可复制话术。
- 至少覆盖洗护到期和沉睡客户两类任务。

### Phase 2：Python 工程脚手架

周期：

- 0.5-1 天。

任务：

- [ ] 按源工程计划 Task 1 创建 `main.py`、`pyproject.toml`、`.env.example`、`app/`、`core/`、`cli/`、`web/`、`agents/`、`tests/`。
- [ ] 安装依赖：`uv sync`。
- [ ] 配置 `.env.example`，支持无 API Key 离线运行。
- [ ] 建立测试夹具 `tests/conftest.py`。
- [ ] 提交：`git add -A && git commit -m "chore: scaffold pet store ai agent"`。

交付物：

- 可安装依赖、可运行测试框架的 Python 项目。

验收命令：

```powershell
uv run pytest tests -q
```

预期：

- 如果只有脚手架，测试可为空或仅跑通 fixtures；不能出现 import error。

### Phase 3：数据模型与数据库初始化

周期：

- 1-2 天。

对应源工程计划：

- Task 2：Database ORM Models。
- Task 3：Database Initialization and Main Entry Point。
- Task 15：Pydantic Schemas。

任务：

- [ ] 实现 SQLAlchemy ORM：门店、员工、客户、宠物、预约、服务记录、试用装记录等核心表。
- [ ] 实现 `init_db()` 和数据库初始化命令。
- [ ] 实现 Pydantic schemas，供 API 和 Web 使用。
- [ ] 写模型测试，验证创建、关联、保存、查询。
- [ ] 提交：`git add app tests main.py && git commit -m "feat: add database models and initialization"`。

交付物：

- 本地 SQLite 数据库可初始化。
- ORM 与 schemas 命名一致。

验收命令：

```powershell
uv run python main.py init-db
uv run pytest tests/test_models.py tests/test_core/test_database.py -q
```

预期：

- 数据库文件创建成功。
- 模型测试通过。

### Phase 4：LLM、Prompt 与 Agent 基座

周期：

- 1-2 天。

对应源工程计划：

- Task 4：LLM Client。
- Task 5：Prompt Template Manager。
- Task 6：BaseAgent Class。
- Task 7：Agent Orchestrator。

任务：

- [ ] 实现 `core/llm.py`，支持 OpenAI-compatible API，API 不可用时返回 `None`。
- [ ] 实现 `core/prompt_templates.py`，包含洗护提醒、沉睡唤醒、试用装回访模板。
- [ ] 实现 `agents/base.py`，封装日志、LLM 调用、模板兜底。
- [ ] 实现 `core/orchestrator.py`，统一注册与调度 Agent。
- [ ] 写 LLM、Prompt、BaseAgent、Orchestrator 单元测试。
- [ ] 提交：`git add core agents tests && git commit -m "feat: add llm prompt and agent orchestration"`。

交付物：

- 不依赖真实 API 也能通过测试。
- LLM 可用时增强话术，不可用时模板降级。

验收命令：

```powershell
uv run pytest tests/test_core/test_llm.py tests/test_core/test_prompt_templates.py tests/test_agents/test_base.py tests/test_core/test_orchestrator.py -q
```

预期：

- 所有测试通过。
- Mock LLM 能返回指定话术。

### Phase 5：核心业务 Agent

周期：

- 2-3 天。

对应源工程计划：

- Task 8：Reminder Agent。
- Task 9：Scheduler Agent。
- Task 10：Sample Agent。
- Task 11：APScheduler Job Registration。

任务：

- [ ] 实现 `ReminderAgent`：生成洗护到期、预流失、沉睡客户任务和话术。
- [ ] 实现 `SchedulerAgent`：管理演示预约、预约状态和基础冲突校验。
- [ ] 实现 `SampleAgent`：生成试用装 T+1/T+4/T+7 回访任务和话术。
- [ ] 实现 `core/scheduler.py`，注册每日扫描任务。
- [ ] 写每个 Agent 的规则测试和调度测试。
- [ ] 提交：`git add agents core tests && git commit -m "feat: add reminder scheduler and sample agents"`。

交付物：

- 规则任务能从数据库记录中生成。
- 每个任务有原因、建议动作和可复制话术。

验收命令：

```powershell
uv run pytest tests/test_agents/test_reminder.py tests/test_agents/test_scheduler.py tests/test_agents/test_sample.py tests/test_core/test_scheduler_jobs.py -q
```

预期：

- 洗护到期、沉睡客户、试用装回访测试通过。
- 近期已跟进或免打扰客户不会重复生成任务。

### Phase 6：CLI、Web 与演示数据

周期：

- 2-4 天。

对应源工程计划：

- Task 12：CLI Commands。
- Task 13：Web App。
- Task 14：Seed Data Script。
- Task 16：Integration Tests。

任务：

- [ ] 实现 CLI：dashboard、customers list、appointments today、reminders pending、sample pending。
- [ ] 实现 FastAPI + Jinja2 Web：base、dashboard、customers、appointments、reminders。
- [ ] 实现 API routes：customers、appointments、reminders、samples。
- [ ] 实现 `seed_data.py`，导入 10 个以上客户、宠物、服务、预约、试用装演示数据。
- [ ] 写集成测试，覆盖初始化、导入数据、生成提醒、查看工作台。
- [ ] 提交：`git add cli web seed_data.py tests && git commit -m "feat: add cli web dashboard and seed data"`。

交付物：

- CLI 可演示完整闭环。
- Web 首页可展示今日预约、待跟进、沉睡客户、试用装回访。

验收命令：

```powershell
uv run python main.py init-db
uv run python main.py seed
uv run python main.py dashboard
uv run python main.py reminders pending
uv run pytest tests/test_cli.py tests/test_integration.py -q
uv run uvicorn web.app:app --reload
```

预期：

- CLI 输出非空统计。
- 浏览器打开 `http://localhost:8000` 能看到 dashboard。
- 集成测试通过。

### Phase 7：README、合规与最终验证

周期：

- 0.5-1 天。

对应源工程计划：

- Task 17：README and Final Polish。

任务：

- [ ] 写 README，说明功能、快速开始、技术栈、项目结构、离线模式。
- [ ] 在 README 和界面文案中明确：不提供健康问诊、疾病诊断、用药建议。
- [ ] 跑完整 CLI/Web 验证。
- [ ] 检查 Git diff，确认没有密钥、个人隐私、真实客户数据。
- [ ] 提交：`git add README.md main.py web && git commit -m "docs: add usage guide and final polish"`。

交付物：

- 可交给下一个 agent 或开发者继续执行的项目说明。

验收命令：

```powershell
uv run pytest tests -q
git diff --check
git status --short
```

预期：

- 测试全部通过。
- diff 无空白错误。
- 未提交变更只包含预期文件。

## 九、种子门店验证计划

目标：

- 用 7-14 天验证门店是否每天使用、是否复制话术、是否产生预约或购买、是否愿意付费。

门店组合：

- 1 家宠物洗护店。
- 1 家宠物美容店。
- 1 家洗护 + 零售综合店。

试点导入数据：

- 客户称呼。
- 手机号或微信昵称。
- 宠物名。
- 宠物类型。
- 服务类型。
- 上次服务时间。
- 备注或偏好。

成功标准：

- 至少 1 家门店在试点期找回 3 个以上老客户，或带来 5 个以上预约。
- 店员每天打开工作台。
- AI 话术被复制发送，而不是只看不做。
- 老板愿意付费或推荐同行。

## 十、验收清单

- [ ] 计划能回答 MVP 核心问题：今天该联系谁、为什么、怎么说。
- [ ] P0 明确排除健康问诊、支付、库存、自动外发、多门店。
- [ ] 数据模型覆盖 P0 全流程。
- [ ] 规则可解释、可复现。
- [ ] AI 输出是人工确认后使用，不自动群发。
- [ ] LLM 不可用时系统仍能运行。
- [ ] CLI 能展示 dashboard、客户、预约、待跟进、试用装任务。
- [ ] Web 首页能展示关键运营指标。
- [ ] 种子门店试点验证真实行为和付费意向，不只收集口头好评。
- [ ] 合规边界避免医疗建议和未经授权触达。

## 十一、执行建议

推荐执行顺序：

1. 如果还没有真实种子门店，先执行 Phase 0-1，用零代码版验证业务。
2. 如果已经决定开发 MVP，直接从 Phase 2 开始，按源工程计划的 17 个 Task 实施。
3. 每完成一个 Phase 就提交一次或多次 commit。
4. 每个 Agent 任务完成后先跑对应测试，再进入下一个任务。
5. 在接企业微信、短信、服务号前，先完成授权、频率限制、退订/免打扰和人工覆盖设计。

两种执行方式：

1. **Subagent-Driven（推荐）**：每个 Phase 或每个源工程 Task 派一个独立子 Agent，完成后由主 Agent 审查。
2. **当前会话执行**：使用 `executing-plans` 分批执行，每个 Phase 后做检查点。
