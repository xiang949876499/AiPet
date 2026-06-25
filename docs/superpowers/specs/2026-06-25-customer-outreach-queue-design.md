# 客户触达队列 — 合并客户机会与客户待办

**日期**: 2026-06-25
**状态**: 设计中
**分支**: codex/ops-agent-subscription

## 问题

Workbench 客户 Tab 下「客户机会」和「客户待办」两个面板信息重叠——两者都在展示"哪些客户需要联系"，
但数据来源不同（`build_customer_opportunities` vs `FollowTask`），用户需要在两个面板之间切换，
增加认知负担。

## 目标

合并为一个「客户触达队列」视图，聚焦一件事：提醒用户给客户发消息，并生成对应话术。

## 设计决策

| 决策点 | 选择 |
|--------|------|
| 核心交互模式 | 消息发送队列：自动生成待触达客户 + 话术 → 逐一确认 → 标记完成 |
| 数据合并策略 | FollowTask 为主，opportunities 补充去重（同一 customer+pet 视为重复，FollowTask 优先） |
| 虚拟条目处理 | 后台自动创建 FollowTask，前端永远只跟 task_id 交互 |
| 用户操作集 | 生成话术 / 编辑话术 / 重新生成 / 复制 / 标记已发送 / 跳过 |

---

## 1. 数据层

### 1.1 新增函数: `build_outreach_queue()`

位置: `services/ops_dashboard.py`

```python
def build_outreach_queue(db_session, store_id: int) -> list[dict]:
```

**逻辑**:

1. 查询所有 `FollowTask`（不限状态），按 `customer_id + pet_id` 建索引
2. 调用 `build_customer_opportunities()` 获取机会列表
3. 遍历 opportunities：
   - 若 `(customer_id, pet_id)` 已存在 FollowTask → 跳过
   - 若不存在 → **自动创建 FollowTask**（status="待处理", ai_message 使用 opportunity 自带 message）
4. 重新查询所有 FollowTask，按优先级排序返回
5. 返回统一队列项 + 统计计数

**排序规则**: 
- 待处理（status="待处理"）排最前 → 再按 task_type 紧迫度（洗护提醒 > 沉睡唤醒 > 会员关怀）

**自动创建 FollowTask 的字段映射**:
```
opportunity.customer_name → 通过 name 反查 customer_id
opportunity.pet_name      → 通过 name + customer_id 反查 pet_id
opportunity.suggested_action → task_type
opportunity.reason         → reason
opportunity.message        → ai_message（预填）
store_id                   → store_id
```

### 1.2 去重键

去重使用 `(customer_id, pet_id)` 组合键。同一客户的不同宠物算不同条目（合理——每只宠物洗护周期不同）。

---

## 2. API 层

### 2.1 新增端点

```
GET /api/customers/outreach-queue?store_id={store_id}
```

放在 `web/routes/customers.py`。

**响应格式**:

```json
{
  "items": [
    {
      "id": 42,
      "customer_id": 1,
      "customer_name": "张三",
      "pet_id": 3,
      "pet_name": "旺财",
      "task_type": "洗护提醒",
      "priority": "high",
      "reason": "旺财距上次洗护已 48 天",
      "suggested_action": "发送洗护预约提醒",
      "ai_message": "张姐，旺财上次洗护已经一个多月...",
      "due_date": "2026-06-26T00:00:00",
      "status": "待处理"
    }
  ],
  "counts": {
    "total": 12,
    "pending_script": 5,
    "ready_to_send": 4,
    "sent_today": 3
  }
}
```

**counts 说明**:
- `pending_script`: status="待处理" 且 ai_message 为空
- `ready_to_send`: status="待处理" 且 ai_message 不为空
- `sent_today`: status="已发送" 且 updated_at 为今天

### 2.2 复用现有接口

| 操作 | 接口 | 说明 |
|------|------|------|
| 生成话术 | `POST /api/reminders/{task_id}/friendly-message` | 不变 |
| 标记已发送 | `POST /api/reminders/{task_id}/send` | 不变 |

### 2.3 新增端点

**跳过任务**:
```
POST /api/reminders/{task_id}/skip
```
逻辑：`task.status = "已跳过"`, `task.result = "已跳过"`, commit。

**保存编辑后的话术**:
```
POST /api/reminders/{task_id}/update-message
Body: { "message": "用户编辑后的话术文本" }
```
逻辑：`task.ai_message = message`, commit，返回更新后的 task payload。
用于前端「编辑」→ 修改 →「保存」的持久化。

---

## 3. 前端

### 3.1 替换范围

**移除**:
- `App.vue` 中 workbench 客户 Tab 下的「客户机会」面板（`.feature-panel` 第一个）
- 「客户待办」面板（`.feature-panel` 第二个）

**替换为**: 单个「客户触达队列」面板，占据全宽（或两栏合并为一栏）。

### 3.2 队列项组件

每条队列项展示：

```
┌──────────────────────────────────────────────────┐
│ 🔴 张三 · 旺财                           [状态标签] │
│ 距上次洗护已 48 天 · 发送洗护预约提醒              │
│ ┌──────────────────────────────────────────────┐ │
│ │ 张姐，旺财上次洗护已经一个多月啦，可以安排一次   │ │
│ │ 基础洗护，充分吹干梳理...              [编辑]   │ │
│ └──────────────────────────────────────────────┘ │
│ [重新生成]  [复制话术]  [标记已发送]  [跳过]      │
└──────────────────────────────────────────────────┘
```

**状态与操作按钮映射**:

| 状态 | 话术状态 | 显示按钮 |
|------|---------|---------|
| 待处理 | 无话术 | `[生成话术]` `[跳过]` |
| 待处理 | 有话术 | `[编辑]` `[重新生成]` `[复制话术]` `[标记已发送]` `[跳过]` |
| 已发送 | — | 灰色展示，无可操作按钮（或仅 `[查看]`） |
| 已跳过 | — | 灰色展示，无可操作按钮 |

### 3.3 顶部统计条

```
客户触达队列                              [刷新]
待生成话术 5  ·  待发送 4  ·  今日已发送 3
```

点击数字可筛选（可选：作为后续迭代）。

### 3.4 交互流程

1. 页面加载 → `GET /api/customers/outreach-queue` → 渲染队列
2. 点击「生成话术」→ `POST /api/reminders/{id}/friendly-message` → 局部更新该项
3. 点击「编辑」→ 话术文本变为可编辑 textarea → 「保存」（调用 `POST /api/reminders/{id}/update-message` 持久化）「取消」（恢复原文本）
4. 点击「重新生成」→ 再次调用 friendly-message → 覆盖原话术
5. 点击「复制话术」→ `navigator.clipboard.writeText()` → toast "已复制"
6. 点击「标记已发送」→ `POST /api/reminders/{id}/send` → 该项变为已发送状态
7. 点击「跳过」→ `POST /api/reminders/{id}/skip` → 该项变为已跳过状态
8. 点击「刷新」→ 重新请求队列数据

### 3.5 数据获取

新增 frontend API 调用（在 `web/static/app.js` 或 Vue setup 中）：

```js
const fetchOutreachQueue = async () => {
  const res = await fetch('/api/customers/outreach-queue');
  return res.json();
};
```

---

## 4. 向后兼容

| 受影响项 | 处理方式 |
|----------|---------|
| Dashboard 页 `opportunities` | 保留不动（dashboard 仍展示关键预警中的 opportunities 计数） |
| Dashboard 页 `action_recommendations` | 保留不动 |
| 旧 workbench 客户 Tab | 完全替换为新队列视图 |
| `build_customer_opportunities()` | 保留，被 dashboard 和新队列复用 |
| `/api/reminders` 列表接口 | 保留不动 |
| `FollowTask` 模型 | 不变，新增 status "已跳过"（已有 "skipped" alias） |

---

## 5. 测试要点

| 测试场景 | 验证点 |
|----------|--------|
| 队列合并去重 | 同一 customer+pet 在 FollowTask 和 opportunities 都存在时只出现一次 |
| 虚拟条目自动创建 | 仅有 opportunity 无 FollowTask 时，调用队列接口后 FollowTask 被创建 |
| 生成话术 | 调用 friendly-message 后 ai_message 字段更新 |
| 编辑话术 | 前端编辑后保存到 ai_message |
| 标记已发送 | 调用 send 后 status 变为 "已发送" |
| 跳过 | 调用 skip 后 status 变为 "已跳过" |
| 空队列 | 无待处理任务时显示空状态 |
| 统计计数 | counts 数字与实际列表一致 |

---

## 6. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `services/ops_dashboard.py` | 修改 | 新增 `build_outreach_queue()` |
| `web/routes/customers.py` | 修改 | 新增 `GET /outreach-queue` 端点 |
| `web/routes/reminders.py` | 修改 | 新增 `POST /{task_id}/skip` 和 `POST /{task_id}/update-message` 端点 |
| `frontend/src/App.vue` | 修改 | 替换客户 Tab 两个面板为队列视图 |
| `tests/test_services/test_ops_dashboard.py` | 修改 | 新增队列合并去重测试 |
| `tests/test_web/test_reminder_friendly_message.py` | 修改 | 新增 skip 端点测试 |

---

## 7. 不做

- 不修改 FollowTask 数据库模型
- 不删除 `build_customer_opportunities()`（dashboard 仍在使用）
- 不在队列中增加批量操作（保持单条操作，降低复杂度）
- 不在本次迭代中增加队列筛选/搜索（后续可加）
