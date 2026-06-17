# 宠店 AI 管家 — Agent 实施设计文档

> 基于《宠店 AI 管家产品设计文档 V1.0 MVP 版》及《宠客AI管家产品设计文档 V1.0》的 Agent 系统实施设计
> 日期：2026-06-17 | 状态：待实施

---

## 一、设计目标

面向社区宠物店、夫妻店、小型宠物生活馆的轻量级私域运营自动化 Agent 工具。用 Python 自主开发，替代 Dify/Coze 等零代码方案，实现：

- 预约自动排期与档期管理
- 老客复购自动化唤醒（洗护周期、寄养预告、沉睡唤醒）
- 试用装回访智能转化
- 营销素材 AI 生成（MVP 可选）

### 设计原则

| 原则 | 说明 |
|------|------|
| 轻量优先 | 拒绝大而全，只做高频刚需，核心依赖 ≤10 个 |
| 自动化优先 | 可规则化的工作全交给 Agent，人工只做异常处理 |
| 离线可靠 | 核心逻辑不依赖 LLM 也能运行（排期校验、周期计算） |
| 模块化 | 每个业务模块是一个独立 Agent，通过调度器协调 |

### 交付形态

- **部署方式**：单店独立部署，Python 后端 + CLI + 轻量 Web 界面
- **技术栈**：Python 3.11+，FastAPI，SQLite，APScheduler
- **LLM**：OpenAI / Claude API（仅用于话术生成和意向识别）
- **周期**：3 周 MVP 交付

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户交互层                                     │
│  ┌───────────────────┐  ┌────────────────────────────────────────┐  │
│  │  CLI (rich 终端)   │  │ Web UI (FastAPI + Jinja2 + Bootstrap) │  │
│  └────────┬──────────┘  └──────────────┬─────────────────────────┘  │
└───────────┼─────────────────────────────┼───────────────────────────┘
            │                             │
┌───────────▼─────────────────────────────▼───────────────────────────┐
│                      API 层 (FastAPI)                                │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────────┐  │
│  │档案API  │ │预约API  │ │复购API  │ │试用API  │ │系统管理API       │  │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───────┬──────────┘  │
└──────┼──────────┼──────────┼──────────┼──────────────┼──────────────┘
       │          │          │          │              │
┌──────▼──────────▼──────────▼──────────▼──────────────▼──────────────┐
│                    Agent 核心层                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                   AgentOrchestrator                             │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │  │
│  │  │ 排期Agent   │ │ 复购Agent   │ │ 试用装Agent │ │ 素材Agent   │  │  │
│  │  │ (离线)      │ │ (LLM增强)   │ │ (LLM增强)   │ │ (LLM驱动)   │  │  │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────┐ ┌──────────────────┐ ┌──────────────────────┐   │
│  │ LLMClient      │ │ Prompt 模板库    │ │ 工具函数库            │   │
│  │ (OpenAI/Claude)│ │ (运营话术模板)    │ │ (日期/消息/统计)      │   │
│  └────────────────┘ └──────────────────┘ └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│                  数据存储层 (SQLite + SQLAlchemy)                     │
│  7 张核心表 + 3 张辅助表                                             │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│              定时任务层 (APScheduler)                                 │
│  ┌───────────────────┐ ┌────────────────┐ ┌───────────────────────┐ │
│  │每日 9:00 复购扫描   │ │到店提醒触发      │ │试用装回访节点触发     │ │
│  └───────────────────┘ └────────────────┘ └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 三层架构说明

| 层级 | 技术 | 职责 |
|------|------|------|
| 交互层 | Rich CLI + FastAPI/Jinja2 | 用户操作入口，数据查看与操作 |
| Agent 核心层 | 自建 BaseAgent 体系 | 业务逻辑编排，LLM 调用，规则引擎 |
| 数据存储层 | SQLite + SQLAlchemy ORM | 持久化所有业务数据 |
| 定时任务层 | APScheduler | 驱动所有自动化流程 |

---

## 三、数据库设计

### 3.1 表关系

```
customers 1──N pets 1──N appointments
pets      1──N service_records
customers 1──N samples
pets      1──N marketing_messages
```

### 3.2 表结构

#### customers（客户表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| wechat_name | TEXT | 微信昵称 |
| phone | TEXT | 手机号 |
| visit_count | INTEGER DEFAULT 0 | 到店次数 |
| tags | TEXT | 消费标签（JSON 数组） |
| level | TEXT DEFAULT 'new' | new/regular/vip |
| last_visit_at | DATETIME | 最近到店时间 |
| status | TEXT DEFAULT 'active' | active/dormant(>90天)/lost |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### pets（宠物表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| customer_id | INTEGER FK→customers | 所属客户 |
| name | TEXT | 宠物名 |
| species | TEXT | 物种（dog/cat/other）|
| breed | TEXT | 品种 |
| age_months | INTEGER | 年龄（月）|
| weight_kg | REAL | 体重 |
| grooming_cycle_days | INTEGER DEFAULT 21 | 洗护周期（天）|
| last_grooming_at | DATETIME | 上次洗护时间 |
| last_boarding_start | DATETIME | 上次寄养开始 |
| last_boarding_end | DATETIME | 上次寄养结束 |
| notes | TEXT | 过敏史/特殊备注 |
| created_at | DATETIME | 创建时间 |

#### appointments（预约表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| pet_id | INTEGER FK→pets | 关联宠物 |
| service_type | TEXT | grooming/wash/boarding |
| appointment_time | DATETIME | 预约时间 |
| duration_minutes | INTEGER | 预计时长 |
| status | TEXT | pending/confirmed/completed/cancelled |
| reminder_sent | BOOLEAN DEFAULT 0 | 到店提醒已发 |
| remark | TEXT | 备注 |
| created_at | DATETIME | 创建时间 |

#### service_records（服务记录表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| pet_id | INTEGER FK→pets | 关联宠物 |
| appointment_id | INTEGER FK→appointments | 关联预约 |
| service_type | TEXT | 服务类型 |
| completed_at | DATETIME | 完成时间 |
| note | TEXT | 本次备注 |
| created_at | DATETIME | 创建时间 |

#### reminder_rules（复购规则表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| rule_type | TEXT UNIQUE | grooming/boarding/dormant |
| trigger_days | INTEGER | 触发天数 |
| advance_days | INTEGER DEFAULT 0 | 提前提醒天数 |
| is_active | BOOLEAN DEFAULT 1 | 是否启用 |
| tone_style | TEXT DEFAULT 'friendly' | friendly/professional/cute |
| created_at | DATETIME | 创建时间 |

#### marketing_messages（消息记录表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| pet_id | INTEGER FK→pets | 关联宠物 |
| rule_type | TEXT | 触发规则类型 |
| content | TEXT | AI 生成话术 |
| status | TEXT DEFAULT 'pending' | pending/sent/converted/skipped |
| sent_at | DATETIME | 发送时间 |
| converted_at | DATETIME | 客户转化时间 |
| created_at | DATETIME | 创建时间 |

#### samples（试用装跟踪表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| customer_id | INTEGER FK→customers | 关联客户 |
| pet_id | INTEGER FK→pets | 关联宠物 |
| product_name | TEXT | 产品名称 |
| product_category | TEXT | 主粮/零食/营养品/驱虫 |
| given_at | DATETIME | 领取时间 |
| followup_stage | INTEGER DEFAULT 0 | 回访阶段(0/1/2/3) |
| intention_level | TEXT | high/medium/low |
| converted | BOOLEAN DEFAULT 0 | 是否转化 |
| notes | TEXT | 备注 |
| created_at | DATETIME | 创建时间 |

---

## 四、Agent 模块设计

### 4.1 BaseAgent 基类

所有 Agent 的统一基类，定义生命周期钩子：

```python
class BaseAgent(ABC):
    def __init__(self, db: Database, llm: LLMClient):
        self.db = db
        self.llm = llm

    @abstractmethod
    def execute(self, context: dict) -> dict:
        """统一执行入口，由 AgentOrchestrator 调用"""
        ...

    def _build_prompt(self, template_name: str, variables: dict) -> str:
        """从 prompt 模板库渲染模板"""
        ...

    def _call_llm(self, prompt: str, system: str = None) -> str:
        """调用 LLM（带重试和错误处理）"""
        ...

    def _save_result(self, table: str, data: dict) -> int:
        """保存结果到数据库"""
        ...
```

### 4.2 排期 Agent（SchedulerAgent）

| 项目 | 说明 |
|------|------|
| LLM 依赖 | 无（完全离线） |
| 核心职责 | 档期校验、预约确认、到店提醒、服务归档 |

**能力清单：**
- `check_conflict(date, time, duration)` → 校验档期是否可用
- `confirm(appointment_id)` → 生成确认通知内容
- `send_reminder(appointment_id)` → 生成到店提醒内容（预约前1天/2小时）
- `complete(appointment_id, note)` → 完成服务并自动归档

**数据流：** 客户扫码 → 校验档期 → 写入预约 → 到店提醒 → 完成服务 → 更新宠物服务时间 → 触发复购规则

### 4.3 复购 Agent（ReminderAgent）

| 项目 | 说明 |
|------|------|
| LLM 依赖 | 话术生成（需要 API） |
| 核心职责 | 周期性扫描到期客户、生成个性化话术、决策升级/跳过 |

**能力清单：**
- `scan_due()` → 扫描所有到期未到店的宠物（三种规则）
- `generate_script(pet_id, rule_type)` → 生成个性化话术（LLM）
- `batch_generate(pet_ids, rule_type)` → 批量生成
- `log_send(message_id)` → 记录已发送
- `log_conversion(message_id)` → 记录客户转化

**三种唤醒场景：**

| 场景 | 触发条件 | 话术重点 |
|------|----------|----------|
| 洗护周期提醒 | 距离上次洗护 ≥ trigger_days | 养护建议 + 预约入口 |
| 寄养档期预告 | 节假日/开学季前 advance_days | 早鸟优惠 + 锁定名额 |
| 沉睡客户唤醒 | 距上次到店 ≥ 90 天 | 专属回归福利 + 限时紧迫感 |

**提示词模板（洗护提醒）：**
```
你是一位宠物店的资深美容师{shop_name}，现在需要给客户{pet_name}的主人发一条洗护提醒。
宠物品种：{breed}，年龄：{age}，上次洗护距今已经{days}天。
请用{tone_style}的语气写一段不超过80字的微信消息：
- 要提到宠物名字
- 给出一个结合当前季节({season})的养护小建议
- 自然引导预约，但不要硬推
```

### 4.4 试用装 Agent（SampleAgent）

| 项目 | 说明 |
|------|------|
| LLM 依赖 | 回访话术生成、意向识别（需要 API） |
| 核心职责 | 节点化自动回访、意向分层、转化引导 |

**能力清单：**
- `check_due_followups()` → 扫描到期待回访的记录
- `generate_followup(sample_id, stage)` → 按阶段生成回访话术
- `identify_intention(sample_id, reply_text)` → 识别客户回复意向
- `generate_promotion(sample_id)` → 对高意向客户生成促单话术

**三阶段回访流程：**

| 阶段 | 时间 | 动作 | LLM |
|------|------|------|-----|
| T+1 | 发放次日 10:00 | 首次关怀，询问适口性 | 生成关怀话术 |
| T+4 | 发放后第4天 | 二次跟进，引导正装 | 生成跟进话术 |
| T+7 | 发放后第7天 | 意向跟进，推送优惠 | 识别意向+生成促单 |

**Intent 识别示例：**
```
分析以下客户回复，判断其对{product_name}的购买意向：
回复内容：{reply}

输出 JSON：
{"intention": "high|medium|low", "reason": "原因"}
- high：询问价格/购买方式/立刻下单
- medium：觉得还不错/考虑一下
- low：不爱吃/不需要/暂时不买
```

### 4.5 素材 Agent（MaterialAgent — MVP 可选）

| 项目 | 说明 |
|------|------|
| LLM 依赖 | 全量依赖 |
| 核心职责 | 朋友圈文案生成、海报提示词、活动方案 |

**能力清单：**
- `generate_post(topic, style)` → 生成朋友圈文案
- `generate_poster_prompt(topic)` → 生成 AI 绘图提示词

### 4.6 AgentOrchestrator 调度器

```python
class AgentOrchestrator:
    """统一调度中心"""

    def __init__(self, db, llm):
        self.agents = {
            'scheduler': SchedulerAgent(db, llm),
            'reminder': ReminderAgent(db, llm),
            'sample': SampleAgent(db, llm),
            'material': MaterialAgent(db, llm),
        }
        self.aps = BackgroundScheduler()
        self._register_jobs()

    def _register_jobs(self):
        # 每日 9:00 扫描复购到期
        self.aps.add_job(self._scan_reminders, 'cron', hour=9, id='reminder_scan')
        # 每 30 分钟检查待发送提醒
        self.aps.add_job(self._check_reminders, 'interval', minutes=30, id='reminder_send')
        # 每日 10:00 检查试用装回访节点
        self.aps.add_job(self._check_samples, 'cron', hour=10, id='sample_followup')

    def execute(self, agent_name: str, context: dict) -> dict:
        """运行指定 Agent"""
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}")
        return agent.execute(context)
```

---

## 五、用户交互设计

### 5.1 CLI 模式（Rich 终端）

基于 `click` + `rich`，完成所有核心操作：

| 命令 | 说明 |
|------|------|
| `python main.py cli` | 进入交互式 CLI |
| `python main.py serve` | 启动 Web 服务 |
| `python main.py init-db` | 初始化数据库 |
| `python main.py import-demo` | 导入演示数据 |

**CLI 交互式命令（内置于 `cli/commands.py`）：**

| 命令 | 操作 |
|------|------|
| `dashboard` | 显示今日概览（预约数/待发送话术/转化率） |
| `customers list` | 客户列表（带搜索/筛选） |
| `customers show <id>` | 客户详情 + 宠物信息 |
| `appointments today` | 今日预约日历 |
| `appointments add` | 手动新增预约 |
| `reminders pending` | 查看待发送话术列表 |
| `reminders send <id>` | 标记话术已发送 |
| `sample pending` | 查看待回访试用装 |
| `sample reply <id>` | 录入客户回复（触发意向识别） |

### 5.2 Web 模式（FastAPI + Jinja2）

简洁的响应式后台界面，包含：

| 页面 | 路径 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 今日预约、待提醒数、转化数据概览 |
| 客户管理 | `/customers` | 客户档案列表、搜索、详情 |
| 预约管理 | `/appointments` | 日历视图、新增/修改/取消 |
| 复购运营 | `/reminders` | 待发送话术预览、一键复制、发送记录 |
| 试用装管理 | `/samples` | 领取记录、回访进度、转化统计 |
| 设置 | `/settings` | 洗护周期、营业时间、话术风格 |

---

## 六、错误处理策略

| 场景 | 处理方式 |
|------|----------|
| LLM API 调用失败 | 重试 2 次 → 降级为模板话术 → 标记告警 |
| 数据库操作异常 | 事务回滚 → 日志记录 → CLI/Web 展示错误提示 |
| APScheduler 任务异常 | 捕获异常 → 日志记录 → 任务自动续跑 |
| 预约冲突 | 业务层校验 → 返回冲突时段建议 |
| 无 LLM 可用 | 核心功能（排期/提醒）正常运行，仅 AI 生成功能降级 |

---

## 七、测试策略

| 层级 | 工具 | 覆盖内容 |
|------|------|----------|
| 单元测试 | pytest | Agent 核心逻辑、数据库模型、工具函数 |
| LLM 测试 | pytest + mock | Prompt 模板渲染、LLM 调用降级逻辑 |
| 集成测试 | pytest + SQLite in-memory | Agent 全流程串联 |
| CLI 测试 | click.testing | 命令解析与输出 |
| API 测试 | httpx | FastAPI 路由响应 |

---

## 八、项目目录结构

```
ai-pet-agent/
├── main.py                    # 入口
├── requirements.txt           # 依赖
├── .env.example               # 环境变量模板
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── config.py              # 配置
│   ├── database.py            # 数据库
│   ├── models.py              # ORM 模型
│   └── schemas.py             # Pydantic 模型
│
├── agents/
│   ├── __init__.py
│   ├── base.py                # BaseAgent 基类
│   ├── scheduler.py           # 排期 Agent
│   ├── reminder.py            # 复购 Agent
│   ├── sample.py              # 试用装 Agent
│   └── material.py            # 素材 Agent
│
├── core/
│   ├── __init__.py
│   ├── llm.py                 # LLM 客户端
│   ├── prompt_templates.py    # Prompt 模板库
│   ├── orchestrator.py        # 调度器
│   └── scheduler.py           # 定时任务
│
├── web/
│   ├── __init__.py
│   ├── app.py                 # FastAPI 应用
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
│
├── cli/
│   ├── __init__.py
│   └── commands.py
│
└── tests/
    ├── __init__.py
    ├── test_agents/
    │   ├── test_scheduler.py
    │   ├── test_reminder.py
    │   └── test_sample.py
    └── test_core/
        ├── test_llm.py
        └── test_orchestrator.py
```

---

## 九、3 周 MVP 实施路线图

| 周 | 日 | 交付物 |
|:--:|:--:|--------|
| **W1** | 1-2 | 项目脚手架、SQLAlchemy 模型、配置管理、环境搭建 |
| | 3-4 | BaseAgent 基类、LLMClient、Prompt 模板库 |
| | 5-7 | **复购 Agent**：扫描逻辑、话术生成、消息存储 |
| **W2** | 8-9 | **排期 Agent**：档期校验、预约管理、到店提醒 |
| | 10-11 | **试用装 Agent**：回访节点、意向识别、转化 |
| | 12-14 | CLI 界面（Rich 面板/表格）+ Web 路由 + 页面模板 |
| **W3** | 15-16 | APScheduler 定时任务集成、全流程联调 |
| | 17 | 种子数据录入、端到端测试 |
| | 18-21 | Bug 修复、README / 使用文档、打包交付 |

**MVP 核心依赖（requirements.txt）：**
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
sqlalchemy>=2.0.30
apscheduler>=3.10.4
openai>=1.30.0
click>=8.1.7
rich>=13.7.0
python-dotenv>=1.0.1
jinja2>=3.1.4
python-multipart>=0.0.9
pydantic>=2.7.0
pytest>=8.2.0
```

---

## 十、设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | 自建轻量 BaseAgent | 拒绝框架黑盒，MVP 阶段完全可控 |
| 数据存储 | SQLite + SQLAlchemy | 单店部署，无需独立数据库服务 |
| LLM 调用层 | 直接 API 调用（非 LangChain） | 减少依赖，Prompt 可直接调试 |
| 定时任务 | APScheduler（进程内） | 单店场景无需 Redis Queue / Celery |
| 前端 | FastAPI + Jinja2 模板 | 零额外依赖，一人开发即可维护 |
| CLI | Click + Rich | 调试友好，也是有效的 MVP 交互方式 |
| Prompt 管理 | YAML 模板文件 + Python 渲染 | 非技术人员可编辑，便于迭代 |
