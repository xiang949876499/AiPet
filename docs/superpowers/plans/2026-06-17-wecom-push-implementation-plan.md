# 企业微信推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为宠物店 AI 复购提醒助手增加企业微信推送能力，先把待跟进任务推给店员确认，再逐步支持客户联系群发和新客户欢迎语。

**Architecture:** 采用“任务生成 -> 推送队列 -> 人工确认 -> 企业微信发送 -> 状态回写”的人控闭环。第一阶段只向企业内部成员推送待办提醒；第二阶段接客户联系群发；第三阶段接外部联系人欢迎语和回调事件。任何客户侧触达都必须经过授权、免打扰和频率控制。

**Tech Stack:** Python 3.11+、uv、FastAPI、SQLAlchemy、SQLite、httpx、pytest、企业微信自建应用 API、企业微信客户联系 API。

**Execution Status 2026-06-18:** 已执行内部通知闭环 Task 1-7，包括企业微信 token client、`PushTask` 模型、推送策略、`FollowTask` 转内部推送任务、发送状态回写、CLI dry-run/发送命令、Web 审核页。已执行 Task 9 企业微信 OAuth 登录与 `Staff` 绑定。客户侧群发 Task 8、回调事件 Task 10、通讯录同步 Task 11 尚未执行。

---

## Scope Decision

### 第一版做

- 企业微信自建应用配置。
- access_token 获取与缓存。
- `FollowTask` 转 `PushTask`。
- 推送待跟进提醒给店员的企业微信内部应用消息。
- 店员确认后再人工发送客户微信。
- 推送状态记录：待确认、已发送、失败、跳过。

### 第二版做

- 客户 `external_userid` 绑定。
- 企业微信客户联系群发任务。
- 群发发送结果回写。
- 客户免打扰、频控、发送失败重试。

### 第三版做

- 外部联系人添加回调。
- 欢迎语 `welcome_code` 发送。
- 回调签名校验与事件落库。

### 明确不做

- 不直接自动私聊客户。
- 不绕过企业微信客户联系权限。
- 不自动发送医疗、诊断、用药相关内容。
- 不存明文企业微信 secret 到数据库。
- 不做个人微信自动化。

## 企业微信能力边界

企业微信有两类容易混淆的消息：

- **自建应用消息**：发送给企业内部成员，用于提醒店员处理待办。适合第一阶段。
- **客户联系消息/群发**：面向外部联系人或客户群，需要客户联系权限、客户绑定关系和发送规则。适合第二阶段。

第一阶段默认只使用自建应用消息，因为它不触碰客户侧自动触达，风险最低。

参考资料：

- 企业微信 API 调用通常先通过 `corpid + corpsecret` 获取 `access_token`。
- 企业微信群发客户能力需要客户联系相关权限。
- 外部联系人欢迎语依赖客户添加事件中的 `welcome_code`，适合新客户首次添加后的短窗口触达。

实现前必须重新核对企业微信官方文档中的接口路径、参数和频率限制。

## 企业微信完整接入扩展计划（2026-06-18）

本节补充完整企业微信接入路径，覆盖登录、账号绑定、内部消息、回调事件、通讯录同步和未来多企业 SaaS 化。当前项目已完成内部应用消息推送闭环，后续接入应在此基础上扩展，避免绕开现有 `PushTask`、`WeComClient`、推送策略和审计日志。

### 接入模式选择

第一阶段采用 **企业内部自建应用**：

- 适合 AIPet 当前门店内部员工使用。
- 支持企业微信 OAuth 登录、成员身份识别、内部应用消息、事件回调。
- 复杂度低于第三方服务商模式。

暂不采用第三方应用/服务商模式，除非后续明确要让多个外部企业自行授权安装 AIPet。服务商模式需要额外维护 `suite_access_token`、`permanent_code`、企业授权状态和多租户隔离。

群机器人 Webhook 只适合作为临时群通知方案，不作为主接入路径。

### 后台配置清单

在企业微信管理后台创建自建应用，并记录：

```text
CorpID      企业 ID
AgentId     应用 ID
Secret      应用 Secret
Token       回调 Token，自定义
AESKey      EncodingAESKey，企业微信生成
```

后台还必须配置：

- 应用可见范围，至少包含需要登录或接收提醒的店员。
- OAuth 可信域名，对应 AIPet 后端回调域名。
- 服务器可信 IP，对应 AIPet 后端出口 IP。
- 回调 URL、Token、EncodingAESKey。

### 环境变量

`.env.example` 已包含基础企业微信变量。后续做 OAuth 登录时补充：

```env
WECOM_REDIRECT_URI=
WECOM_OAUTH_ENABLED=false
WECOM_CALLBACK_ENABLED=false
WECOM_CONTACT_SYNC_ENABLED=false
```

约束：

- `WECOM_APP_SECRET`、`WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY` 只允许放环境变量或密钥管理系统。
- 不把 Secret、Token、AESKey 写入数据库、日志或前端页面。
- 测试环境必须使用 fake client，不调用真实企业微信 API。

### access_token 管理

继续使用现有 `core/wecom_client.py` 作为企业微信 API 入口。

要求：

- 通过 `corpid + corpsecret` 获取 `access_token`。
- 缓存 token，按 `expires_in` 提前 5-10 分钟刷新。
- 接口返回 `invalid access_token` 时允许刷新后重试一次。
- 所有调用记录 `errcode`、`errmsg` 和业务上下文，但不记录敏感凭证。

### OAuth 登录与账号绑定

新增目标：企业微信内打开 AIPet 时，能识别当前企业成员并绑定到本地 `Staff`。

建议新增接口：

```text
GET /wecom/oauth/start
GET /wecom/oauth/callback
```

流程：

```text
用户进入企业微信应用
 -> AIPet 跳转企业微信 OAuth
 -> 企业微信回调并携带 code
 -> 后端用 code + access_token 换取 UserID
 -> 查询或创建本地 Staff 绑定
 -> 写入登录态
 -> 跳转 Web 工作台
```

建议扩展 `Staff`：

```python
wecom_userid: Mapped[str | None]
wecom_corp_id: Mapped[str | None]
wecom_name: Mapped[str | None]
wecom_avatar: Mapped[str | None]
wecom_bound_at: Mapped[datetime | None]
```

验收标准：

- 企业微信内可完成 OAuth 登录。
- 后端能正确拿到企业微信 `UserID`。
- `UserID` 能绑定到本地 `Staff`。
- 非当前企业 `corp_id` 的登录请求会被拒绝。

### 内部应用消息

当前项目已经完成内部推送闭环，后续保持以下边界：

- 内部应用消息只发给店员，不直接发给外部客户。
- 所有发送动作必须通过 `PushTask` 记录。
- `send-internal` 默认支持 `--dry-run`。
- 真实发送必须要求 `WECOM_INTERNAL_NOTIFY_ENABLED=true`。
- 失败必须写回 `PushTask.error_message`。

后续可增加消息类型：

- 文本消息。
- Markdown 消息。
- 任务卡片消息，用于店员确认或跳转工作台。

### 回调事件

新增目标：接收企业微信事件，先完成验证、解密、落库，再逐步驱动业务。

建议新增接口：

```text
GET  /wecom/callback   # URL 验证
POST /wecom/callback   # 事件接收
```

要求：

- 校验 `msg_signature`。
- 使用 `EncodingAESKey` 解密消息。
- 解析事件类型。
- 原始事件和解密后事件均落库。
- 事件处理失败不影响企业微信回包，失败原因进入日志。

建议新增表：

```text
wecom_event_logs
- id
- corp_id
- event_type
- from_user
- raw_payload
- decrypted_payload
- process_status
- error_message
- received_at
```

第一版只处理：

- URL 验证。
- 事件落库。
- 用户进入应用或点击菜单事件。

暂不直接把回调事件用于客户侧自动触达。

### 通讯录同步

新增目标：减少手工维护店员企业微信 UserID。

建议流程：

```text
定时任务
 -> 拉取部门列表
 -> 拉取部门成员
 -> 按 corp_id + userid upsert Staff 绑定信息
 -> 标记禁用或离职成员
```

要求：

- 同步任务默认关闭：`WECOM_CONTACT_SYNC_ENABLED=false`。
- 同步只更新企业微信身份字段，不覆盖门店业务字段。
- 删除或离职成员只标记状态，不物理删除。

### 客户联系与群发

客户侧触达继续作为第二阶段能力，必须受以下策略保护：

- `WECOM_CUSTOMER_SEND_ENABLED=true` 才允许真实调用客户侧 API。
- 客户必须有 `external_userid`。
- 客户必须满足 `push_consent_status="granted"`。
- `do_not_disturb=True` 时禁止发送。
- 医疗、诊断、用药、治疗相关内容禁止自动客户侧发送。
- 每次客户侧发送必须先生成任务并经过人工确认。

客户侧发送计划继续以 `Task 8: Customer Contact Group Send Design Stub` 为入口，不和内部应用消息混用。

### SaaS 多企业扩展预留

如果 AIPet 后续改为多企业 SaaS，需要新增多租户层：

```text
wecom_tenants
- id
- corp_id
- agent_id
- auth_type
- permanent_code
- status
- authorized_at
- revoked_at
```

所有企业微信相关表必须带 `corp_id` 或 `tenant_id`：

- `Staff`
- `PushTask`
- `wecom_event_logs`
- `wecom_message_logs`
- 客户外部联系人绑定表

在切换到第三方服务商模式前，不要把 `corp_id` 假设为全局唯一常量散落在业务代码中，应通过配置或租户上下文传入。

### 实施顺序

新增任务建议排在已完成的内部推送闭环之后：

```text
Task 9: OAuth 登录与 Staff 绑定（已完成 2026-06-18）
Task 10: 企业微信回调 URL 验证与事件落库
Task 11: 通讯录成员同步
Task 12: Markdown/任务卡片消息
Task 13: 多企业 SaaS 化设计预留
```

### Task 9: OAuth 登录与 Staff 绑定（已完成 2026-06-18）

**Files:**

- Modified: `core/wecom_client.py`
- Modified: `app/config.py`
- Modified: `app/models.py`
- Modified: `app/database.py`
- Modified: `web/app.py`
- Modified: `.env.example`
- Created: `services/wecom_oauth.py`
- Tests: `tests/test_core/test_wecom_client.py`
- Tests: `tests/test_services/test_wecom_oauth.py`
- Tests: `tests/test_web_wecom_oauth.py`

已实现：

- `WeComClient.get_oauth_userid(code)` 调用企业微信 OAuth 用户信息接口获取 `UserID`。
- `WeComClient.get_user_detail(userid)` 获取企业微信成员详情，用于绑定展示字段。
- `Staff` 增加 `wecom_corp_id`、`wecom_name`、`wecom_avatar`、`wecom_bound_at`。
- SQLite 兼容迁移补齐新增 `staff` 字段。
- `bind_wecom_staff()` 按 `wecom_userid` 更新已有店员，找不到时在首个门店下创建店员。
- `GET /wecom/oauth/start` 生成企业微信 OAuth 跳转。
- `GET /wecom/oauth/callback` 用 `code` 绑定店员，并设置 `aipet_staff_id` 和 `aipet_wecom_userid` HttpOnly cookie。
- 新增配置：`WECOM_REDIRECT_URI`、`WECOM_OAUTH_ENABLED`、`WECOM_CALLBACK_ENABLED`、`WECOM_CONTACT_SYNC_ENABLED`。

验证：

```powershell
uv run pytest tests/test_core/test_wecom_client.py tests/test_services/test_wecom_oauth.py tests/test_web_wecom_oauth.py -q
```

结果：

```text
8 passed
```

### 风险与验收

主要风险：

- 可信域名未配置导致 OAuth 回调失败。
- 应用可见范围不包含目标店员导致无法登录或收不到消息。
- 可信 IP 未配置导致 API 调用失败。
- access_token 重复获取导致限流。
- 回调加解密实现不完整导致验签失败。
- 客户侧能力绕过人工确认和合规策略。

最终验收：

- 店员可通过企业微信 OAuth 进入 AIPet。
- 店员 `Staff.wecom_userid` 可自动绑定或同步。
- 内部应用消息仍通过 `PushTask` 发送和审计。
- 企业微信回调 URL 验证通过。
- POST 事件可验签、解密、落库。
- 客户侧真实发送默认关闭，且受授权、免打扰、频控和内容安全策略保护。

## File Structure

```text
app/
├── config.py                  # 新增企业微信环境变量
├── models.py                  # 新增 PushTask / WeComBinding 字段或表
└── schemas.py                 # 新增 PushTaskRead / PushTaskCreate

core/
├── wecom_client.py            # 企业微信 token 和 API 封装
└── push_policy.py             # 免打扰、频控、人工确认策略

services/
├── __init__.py
├── push_tasks.py              # FollowTask -> PushTask
└── wecom_push.py              # 发送内部应用消息、客户群发任务

web/
├── app.py                     # 增加推送任务页面路由
└── templates/
    └── push_tasks.html        # 推送任务审核页

tests/
├── test_core/
│   ├── test_wecom_client.py
│   └── test_push_policy.py
├── test_services/
│   ├── test_push_tasks.py
│   └── test_wecom_push.py
└── test_web_push.py
```

## Data Model

### Modify `app/models.py`

新增 `Customer` 字段：

```python
external_userid: Mapped[str | None] = mapped_column(String(120))
push_consent_status: Mapped[str] = mapped_column(String(40), default="unknown")
```

新增 `Staff` 字段：

```python
wecom_userid: Mapped[str | None] = mapped_column(String(120))
```

新增 `PushTask` 表：

```python
class PushTask(Base):
    __tablename__ = "push_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    follow_task_id: Mapped[int | None] = mapped_column(ForeignKey("follow_tasks.id"))
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    receiver_type: Mapped[str] = mapped_column(String(40), nullable=False)
    receiver_id: Mapped[str] = mapped_column(String(160), nullable=False)
    scene: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

状态枚举：

```text
pending      待确认
approved     已确认
sent         已发送
failed       发送失败
skipped      策略跳过
cancelled    人工取消
```

渠道枚举：

```text
wecom_internal        企业微信内部应用消息
wecom_customer_group  企业微信客户联系群发
wecom_welcome         外部联系人欢迎语
manual               人工复制发送
```

## Environment Variables

修改 `.env.example`：

```env
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_APP_SECRET=
WECOM_TOKEN=
WECOM_ENCODING_AES_KEY=
WECOM_INTERNAL_NOTIFY_ENABLED=false
WECOM_CUSTOMER_SEND_ENABLED=false
```

规则：

- `WECOM_APP_SECRET` 只放环境变量，不写入数据库。
- 测试环境用 mock client，不访问真实企业微信。
- `WECOM_CUSTOMER_SEND_ENABLED=false` 时，客户侧推送只能生成任务，不能发送。

## Task 1: WeCom Config And Token Client

**Files:**
- Modify: `app/config.py`
- Create: `core/wecom_client.py`
- Test: `tests/test_core/test_wecom_client.py`

- [ ] **Step 1: Write failing tests**

```python
def test_wecom_client_returns_token_from_cache():
    client = WeComClient(corp_id="cid", app_secret="sec", token_fetcher=lambda: {"access_token": "abc", "expires_in": 7200})
    assert client.get_access_token() == "abc"
    assert client.get_access_token() == "abc"


def test_wecom_client_refuses_without_credentials():
    client = WeComClient(corp_id="", app_secret="")
    assert client.get_access_token() is None
```

Run:

```powershell
uv run pytest tests/test_core/test_wecom_client.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'core.wecom_client'
```

- [ ] **Step 2: Implement `WeComClient`**

Required behavior:

- `get_access_token()` returns cached token if not expired.
- If credentials are missing, return `None`.
- If API fails, return `None` and expose last error.
- `send_internal_text(to_user, content)` posts to enterprise app message API when token exists.
- All HTTP calls must be injectable for tests.

- [ ] **Step 3: Run tests**

```powershell
uv run pytest tests/test_core/test_wecom_client.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Commit**

```powershell
git add app/config.py core/wecom_client.py tests/test_core/test_wecom_client.py
git commit -m "feat: add enterprise wechat token client"
```

## Task 2: PushTask Data Model

**Files:**
- Modify: `app/models.py`
- Modify: `app/schemas.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Add failing model test**

```python
def test_push_task_records_channel_receiver_and_status(db_session, sample_records):
    from app.models import PushTask

    task = PushTask(
        store_id=sample_records["store"].id,
        follow_task_id=None,
        channel="wecom_internal",
        receiver_type="staff",
        receiver_id="zhang_staff",
        scene="repurchase_reminder",
        content="豆豆该洗护了，请跟进。",
    )
    db_session.add(task)
    db_session.commit()

    saved = db_session.query(PushTask).one()
    assert saved.status == "pending"
    assert saved.channel == "wecom_internal"
```

Run:

```powershell
uv run pytest tests/test_models.py -q
```

Expected:

```text
FAIL with ImportError: cannot import name 'PushTask'
```

- [ ] **Step 2: Implement model and schema**

Add:

- `PushTask` ORM model.
- `FollowTask.push_tasks` relationship.
- `PushTaskRead` schema in `app/schemas.py`.

- [ ] **Step 3: Run model tests**

```powershell
uv run pytest tests/test_models.py -q
```

Expected:

```text
All model tests pass
```

- [ ] **Step 4: Commit**

```powershell
git add app/models.py app/schemas.py tests/test_models.py
git commit -m "feat: add push task model"
```

## Task 3: Push Policy

**Files:**
- Create: `core/push_policy.py`
- Test: `tests/test_core/test_push_policy.py`

- [ ] **Step 1: Write failing tests**

```python
def test_policy_blocks_do_not_disturb_customer(sample_records):
    customer = sample_records["customer"]
    customer.do_not_disturb = True
    policy = PushPolicy()
    assert policy.can_send_to_customer(customer, scene="repurchase_reminder") is False


def test_policy_blocks_medical_content(sample_records):
    customer = sample_records["customer"]
    policy = PushPolicy()
    assert policy.validate_content("建议用药治疗皮肤病", customer) == "medical_content_blocked"
```

Run:

```powershell
uv run pytest tests/test_core/test_push_policy.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'core.push_policy'
```

- [ ] **Step 2: Implement policy**

Rules:

- `customer.do_not_disturb=True` blocks customer-side push.
- `push_consent_status != "granted"` blocks customer-side push.
- Medical terms block all customer-side push: `诊断`、`用药`、`治疗`、`处方`、`皮肤病`、`抽搐`、`大出血`。
- Same customer + same scene cannot send more than once within 7 days.
- Internal staff notification is allowed even when customer-side push is blocked.

- [ ] **Step 3: Run tests**

```powershell
uv run pytest tests/test_core/test_push_policy.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Commit**

```powershell
git add core/push_policy.py tests/test_core/test_push_policy.py
git commit -m "feat: add push safety policy"
```

## Task 4: FollowTask To PushTask

**Files:**
- Create: `services/__init__.py`
- Create: `services/push_tasks.py`
- Test: `tests/test_services/test_push_tasks.py`

- [ ] **Step 1: Write failing test**

```python
def test_create_internal_push_task_from_follow_task(db_session, sample_records):
    from app.models import FollowTask, PushTask, Staff
    from services.push_tasks import create_internal_push_task

    staff = Staff(store_id=sample_records["store"].id, name="小王", wecom_userid="wang")
    follow = FollowTask(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        task_type="洗护提醒",
        priority="高",
        reason="豆豆上次洗护距今 24 天",
        suggested_action="发送温和预约提醒",
        ai_message="张姐，豆豆该洗护了。",
    )
    db_session.add_all([staff, follow])
    db_session.commit()

    push_task = create_internal_push_task(db_session, follow.id, staff.id)

    assert push_task.channel == "wecom_internal"
    assert push_task.receiver_id == "wang"
    assert "豆豆" in push_task.content
```

Run:

```powershell
uv run pytest tests/test_services/test_push_tasks.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'services'
```

- [ ] **Step 2: Implement service**

`create_internal_push_task(db_session, follow_task_id, staff_id)` must:

- Load `FollowTask` and `Staff`.
- Require `staff.wecom_userid`.
- Create `PushTask(channel="wecom_internal", receiver_type="staff")`.
- Set content to include customer name, pet name, reason, and AI message.
- Return the created `PushTask`.

- [ ] **Step 3: Run tests**

```powershell
uv run pytest tests/test_services/test_push_tasks.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 4: Commit**

```powershell
git add services tests/test_services/test_push_tasks.py
git commit -m "feat: create push tasks from follow tasks"
```

## Task 5: Internal WeCom Notification Sender

**Files:**
- Create: `services/wecom_push.py`
- Test: `tests/test_services/test_wecom_push.py`

- [ ] **Step 1: Write failing tests**

```python
def test_send_internal_push_task_marks_sent(db_session, push_task_factory):
    from services.wecom_push import send_push_task

    push_task = push_task_factory(channel="wecom_internal", receiver_id="wang")
    fake_client = FakeWeComClient(result={"errcode": 0, "errmsg": "ok"})

    result = send_push_task(db_session, push_task.id, fake_client)

    assert result["sent"] is True
    assert push_task.status == "sent"
    assert push_task.sent_at is not None


def test_send_internal_push_task_records_failure(db_session, push_task_factory):
    from services.wecom_push import send_push_task

    push_task = push_task_factory(channel="wecom_internal", receiver_id="wang")
    fake_client = FakeWeComClient(result={"errcode": 40014, "errmsg": "invalid access_token"})

    result = send_push_task(db_session, push_task.id, fake_client)

    assert result["sent"] is False
    assert push_task.status == "failed"
    assert "invalid access_token" in push_task.error_message
```

Run:

```powershell
uv run pytest tests/test_services/test_wecom_push.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'services.wecom_push'
```

- [ ] **Step 2: Implement sender**

`send_push_task(db_session, push_task_id, wecom_client)` must:

- Load `PushTask`.
- Only send when `status in ["pending", "approved"]`.
- For `wecom_internal`, call `wecom_client.send_internal_text(receiver_id, content)`.
- Mark `sent` on `errcode == 0`.
- Mark `failed` and save `error_message` otherwise.

- [ ] **Step 3: Run tests**

```powershell
uv run pytest tests/test_services/test_wecom_push.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Commit**

```powershell
git add services/wecom_push.py tests/test_services/test_wecom_push.py
git commit -m "feat: send internal enterprise wechat push tasks"
```

## Task 6: CLI For Push Tasks

**Files:**
- Modify: `main.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI test**

```python
def test_cli_lists_and_sends_push_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'push.db'}")
    runner = CliRunner()
    runner.invoke(cli, ["init-db"])
    runner.invoke(cli, ["seed"])

    list_result = runner.invoke(cli, ["push", "list"])
    assert list_result.exit_code == 0
    assert "推送任务" in list_result.output

    send_result = runner.invoke(cli, ["push", "send-internal", "--dry-run"])
    assert send_result.exit_code == 0
    assert "dry-run" in send_result.output
```

Run:

```powershell
uv run pytest tests/test_cli.py -q
```

Expected:

```text
FAIL because command 'push' does not exist
```

- [ ] **Step 2: Implement CLI commands**

Add:

```text
uv run python main.py push list
uv run python main.py push create-internal --follow-task-id 1 --staff-id 1
uv run python main.py push send-internal --dry-run
```

Behavior:

- `push list` displays pending push tasks.
- `push create-internal` creates an internal staff push task.
- `push send-internal --dry-run` prints what would be sent without calling WeCom.
- `push send-internal` sends pending internal tasks only when `WECOM_INTERNAL_NOTIFY_ENABLED=true`.

- [ ] **Step 3: Run CLI tests**

```powershell
uv run pytest tests/test_cli.py -q
```

Expected:

```text
All CLI tests pass
```

- [ ] **Step 4: Commit**

```powershell
git add main.py tests/test_cli.py
git commit -m "feat: add push task cli"
```

## Task 7: Web Push Review Page

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/push_tasks.html`
- Test: `tests/test_web_push.py`

- [ ] **Step 1: Add failing web test**

```python
def test_push_tasks_page_renders_pending_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'web_push.db'}")
    init_db()
    session = SessionLocal()
    seed_demo_data(session)
    create_one_push_task(session)
    session.close()

    client = TestClient(create_app())
    response = client.get("/push-tasks")

    assert response.status_code == 200
    assert "推送任务" in response.text
    assert "待确认" in response.text
```

Run:

```powershell
uv run pytest tests/test_web_push.py -q
```

Expected:

```text
FAIL with 404 Not Found or missing template
```

- [ ] **Step 2: Implement page**

Page must show:

- 推送渠道。
- 接收人。
- 场景。
- 内容。
- 状态。
- 错误信息。

No send button in first web version. Sending stays in CLI until policy is proven.

- [ ] **Step 3: Run web tests**

```powershell
uv run pytest tests/test_web_push.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 4: Commit**

```powershell
git add web/app.py web/templates/push_tasks.html tests/test_web_push.py
git commit -m "feat: add push task review page"
```

## Task 8: Customer Contact Group Send Design Stub

**Files:**
- Create: `docs/wecom-customer-send.md`
- Test: `tests/test_core/test_push_policy.py`

- [ ] **Step 1: Add policy tests for customer-side blocks**

```python
def test_customer_send_requires_granted_consent(sample_records):
    customer = sample_records["customer"]
    customer.external_userid = "wm_external"
    customer.push_consent_status = "unknown"
    assert PushPolicy().can_send_to_customer(customer, "repurchase_reminder") is False
```

- [ ] **Step 2: Write docs**

Document must include:

- Customer-side sending is disabled by default.
- Required customer fields: `external_userid`, `push_consent_status`, `do_not_disturb`.
- Required enterprise permissions: customer contact and customer group send.
- Sending flow: create task -> approve -> call WeCom -> result query -> status update.
- Rollback plan: disable `WECOM_CUSTOMER_SEND_ENABLED`.

- [ ] **Step 3: Run docs-adjacent tests**

```powershell
uv run pytest tests/test_core/test_push_policy.py -q
```

Expected:

```text
All push policy tests pass
```

- [ ] **Step 4: Commit**

```powershell
git add docs/wecom-customer-send.md tests/test_core/test_push_policy.py
git commit -m "docs: document enterprise wechat customer send policy"
```

## Final Verification

Run:

```powershell
uv run pytest tests -q
git diff --check
git status --short
```

Expected:

```text
All tests pass
No whitespace errors
Only expected untracked product source documents remain
```

After the final commit, update CodeGraph:

```powershell
codegraph sync
```

## Self-Review Checklist

- [ ] Internal staff push is implemented before customer-side push.
- [ ] Customer-side push is gated by `WECOM_CUSTOMER_SEND_ENABLED`.
- [ ] No secret is committed.
- [ ] Medical content is blocked by policy.
- [ ] `do_not_disturb` blocks customer-side push.
- [ ] All sends are represented as `PushTask` rows.
- [ ] Failures are persisted with `error_message`.
- [ ] CLI supports dry-run before real send.
- [ ] Web page reviews tasks but does not send in first version.
- [ ] Tests use fake clients and never call real WeCom APIs.

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-06-17-wecom-push-implementation-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using `executing-plans`, batch execution with checkpoints.
