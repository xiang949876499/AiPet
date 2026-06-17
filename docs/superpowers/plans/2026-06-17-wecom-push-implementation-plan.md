# 企业微信推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为宠物店 AI 复购提醒助手增加企业微信推送能力，先把待跟进任务推给店员确认，再逐步支持客户联系群发和新客户欢迎语。

**Architecture:** 采用“任务生成 -> 推送队列 -> 人工确认 -> 企业微信发送 -> 状态回写”的人控闭环。第一阶段只向企业内部成员推送待办提醒；第二阶段接客户联系群发；第三阶段接外部联系人欢迎语和回调事件。任何客户侧触达都必须经过授权、免打扰和频率控制。

**Tech Stack:** Python 3.11+、uv、FastAPI、SQLAlchemy、SQLite、httpx、pytest、企业微信自建应用 API、企业微信客户联系 API。

**Execution Status 2026-06-17:** 已执行内部通知闭环 Task 1-7，包括企业微信 token client、`PushTask` 模型、推送策略、`FollowTask` 转内部推送任务、发送状态回写、CLI dry-run/发送命令、Web 审核页。客户侧群发 Task 8 尚未执行。

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
