# UX 改进 & 数据导入增强 设计文档

> 日期: 2026-06-25 · 状态: 待实现

## 概述

三个改进项：
1. **侧边栏改进** — 导航项放大、加快捷入口、填满空白
2. **工作台与数据看板拆分** — 各司其职，不再重复展示相同数据
3. **客户数据导入增强** — CSV 支持消费记录，放入客户管理页

范围：仅 Vue SPA（`frontend/src/App.vue`），不改动 Jinja2 模板侧。

---

## 1. 侧边栏改进

### 现状

Vue SPA 侧边栏 6 个导航项，无快捷入口区，底部只有门店信息。导航项紧凑，下方空白较大。

### 改动

**导航项尺寸**：
- 字号 14px → 15px
- 图标 18px → 22px
- 行高 padding 略微增加，视觉上更饱满

**新增快捷入口区**（底部、门店信息上方）：

```
── 快捷入口 ──
  导入客户  活动方案  AI 顾问  授权额度
```

与 Jinja2 `_layout.html` 侧边栏的快捷入口保持一致。

**导航结构**（共 6 项，不变）：
```
工作台 → AI 助手 → 客户管理 → 营销活动 → 任务中心 → 数据看板
```

### 涉及文件

- `frontend/src/App.vue` — `<aside class="sidebar">` 模板与对应样式

---

## 2. 工作台 vs 数据看板拆分

### 现状

`activeView === 'dashboard'`（工作台）和 `activeView === 'reports'`（数据看板）展示几乎相同的内容：KPI 卡片、经营漏斗、任务列表。用户感知重复。

### 拆分方案

两者从同一个 `/api/workbench` 获取数据，前端按视图拆分使用。

#### 工作台（dashboard） — "今天做什么"

| 区块 | 内容 | 来源字段 |
|------|------|----------|
| 今日概览 | 待跟进 X 位 / 内容 Y 条 / 带回 ¥Z | `metrics` |
| 待跟进任务 | 完整列表，点击进入单客跟进 | `reminders`（全部） |
| 内容草稿 | 当天待发布列表，可复制/标记 | `content_items`（全部） |
| 客户机会 | 优先维护客户卡片 | `opportunities` |
| 快捷动作 | 新建诊断 / 生成内容 / 导入客户 | `quick_actions` |

不再展示：转化漏斗、客户健康、触达策略对比。

#### 数据看板（reports） — "经营怎么样"

| 区块 | 内容 | 来源字段 |
|------|------|----------|
| 转化漏斗 | 触达 → 回复 → 到店，可视化 | `conversion_funnel` |
| 客户健康 | 活跃/沉睡/流失 分布 | `customer_health` |
| 触达策略效果 | 各策略触达量对比 | `approach_comparison` |
| 关键指标 | 回复率、带回收入、月到店量、周营收 | `metrics` |
| 数据摘要 | 前端拼接的关键结论文本 | 前端计算 |

不再展示：任务列表、内容草稿、客户机会。

#### 数据流

```
/api/workbench (GET)
  └─ get_workbench() → build_tiered_dashboard()
       ├─ metrics (ai_metrics)
       ├─ ops_metrics
       ├─ conversion_funnel     ← 仅看板使用
       ├─ customer_health       ← 仅看板使用
       ├─ approach_comparison   ← 仅看板使用
       ├─ opportunities         ← 仅工作台使用
       ├─ reminders[]           ← 仅工作台使用
       ├─ content_items[]       ← 仅工作台使用
       └─ quick_actions[]       ← 仅工作台使用
```

无需新增后端接口。现有 `workbench.value` 在前端 `data` computed 中已包含所有字段，`dashboard` 和 `reports` 视图各自取需要的子集渲染。

### 涉及文件

- `frontend/src/App.vue` — dashboard 模板区、reports 模板区

---

## 3. 客户数据导入增强

### 现状

`services/customer_import.py` 已支持 CSV 导入客户+宠物基本信息，消费记录仅生成一条 amount=0 的占位 ServiceRecord。

Jinja2 模板 `customers_import.html` 提供上传/预览/导入功能，但 Vue SPA 客户管理页无入口。

### 改进目标

1. **CSV 增加消费字段**：到店日期、服务项目、消费金额、备注
2. **Vue SPA 客户管理页**添加导入入口和导入流程
3. **后端导入逻辑增强**：解析消费字段、创建真实 ServiceRecord

### CSV 表头

```
客户姓名,手机号,微信名,宠物名,宠物类型,品种,到店日期,服务项目,消费金额,备注
```

> 相比旧版：模板中去掉"洗护周期天数"列（系统可从到店频率自动推算），"最近到店"改为"到店日期"（每次消费一行）。旧 CSV 中的旧列名仍可被解析，不会报错，但 `care_cycle_days` 值不再使用（改为自动推算）。

### 导入规则

| 规则 | 行为 |
|------|------|
| 手机号匹配已有客户 | 更新姓名/微信名，不新建 |
| 同一客户+同一天多条 | 合并为一次到店，金额累加，创建多条 ServiceRecord |
| 服务项目不在 [洗护, 美容, 商品, 寄养] | 标黄警告，仍导入（归为"其他"） |
| 缺少客户姓名 | 跳过该行，计入 skipped |
| 到店日期为空 | 跳过消费记录行，仅导入客户信息 |
| 消费金额为空或非数字 | 默认 0 |

### 模板示例

```csv
客户姓名,手机号,微信名,宠物名,宠物类型,品种,到店日期,服务项目,消费金额,备注
张女士,13800001111,豆豆妈妈,豆豆,狗,比熊,2026-06-20,洗护,128,
张女士,13800001111,豆豆妈妈,豆豆,狗,比熊,2026-06-20,商品,89,狗粮3kg
李先生,13900002222,,咪咪,猫,英短,2026-06-18,美容,268,造型修剪
王姐,13700003333,小七主人,小七,狗,柯基,2026-06-15,寄养,300,3天
```

### Vue SPA 导入流程（客户管理页内）

客户管理页（`activeView === 'customers'`）顶部增加操作栏：

```
[导入客户]  [下载模板]                   搜索框...
```

点击"导入客户"弹出导入面板，三步走：

1. **上传** — 文件选择器 + 拖拽区，接受 .csv
2. **预检** — 调用 `/api/customers/import/preview`（JSON 版），展示：
   - 总行数 / 可导入数 / 跳过数
   - 摘要：新增客户 X 位，更新 Y 位，消费记录 Z 条，总金额 ¥W
   - 警告列表（逐行展示问题）
3. **导入** — 确认后执行，展示结果卡片：
   - 新增/更新客户数、新增宠物数、消费记录数、跳过数
   - "查看客户列表"按钮和"生成今日提醒"按钮

### 后端改动

**新增 API（JSON 版，供 Vue SPA 使用）**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/customers/import/preview` | 上传 CSV 返回 JSON 预检结果 |
| POST | `/api/customers/import` | 上传 CSV 执行导入，返回 JSON 结果 |
| GET | `/api/customers/import/template` | 下载 CSV 模板（已存在，复用） |

> 两个新的 JSON API 复用 `services/customer_import.py` 的核心逻辑，仅包装为 JSON 输入输出。旧 Jinja2 页面版（Form POST + Redirect）保持不变。

**`services/customer_import.py` 改动**：

- `HEADER_ALIASES` 增加新字段：`service_date`（到店日期）、`service_type`（服务项目）、`amount`（消费金额）、`note`（备注）
- 去掉 `care_cycle_days` 别名（旧 CSV 仍兼容，不报错）
- `import_customers_from_csv()` 在创建/更新客户后，对每一行：
  - 解析 `service_date`、`service_type`、`amount`、`note`
  - 创建真实 `ServiceRecord`（含 type + amount），替代旧的 `_ensure_service_record()`（之前只创建 amount=0 的占位记录）
  - 更新 `Customer.last_visit_time` 和 `Customer.visit_count`
- `preview_customers_from_csv()` 增加消费字段的校验（金额非数字警告、服务项目不在列表警告）

**后续分析预留**（本次不实现，仅确保数据就绪）：
- `ServiceRecord` 已有 `service_type`, `amount`, `service_time` 字段
- 后续可查询：本周/本月消费汇总、按服务项目分类统计、客户消费频次排行

### 涉及文件

- `services/customer_import.py` — 导入逻辑增强
- `web/routes/customers.py` — 新增 JSON API 端点
- `frontend/src/App.vue` — 客户管理页导入面板
- `web/app.py` — 旧 Jinja2 端点保持不变（无需改动）

---

## 边界条件 & 错误处理

| 场景 | 处理 |
|------|------|
| CSV 文件为空 | 预检提示"文件为空" |
| CSV 编码非 UTF-8 | 尝试 UTF-8 BOM，失败则提示编码错误 |
| 全部行被跳过 | 导入结果 skipped = total，提示"没有可导入的数据" |
| 门店不存在 | 提示"请先完成初始化" |
| 文件超过 10MB | 前端限制，提示"文件过大" |
| 并发导入 | 不做特殊处理（单用户场景） |

## 测试要点

- CSV 导入新客户 + 消费记录
- CSV 更新已有客户（手机号匹配）
- 同一天多条消费合并
- 空到店日期跳过消费
- 服务项目不在列表中仍可导入
- 工作台与看板数据不重复
- 侧边栏快捷入口可点击跳转

## 不做什么

- 不新增历史快照表（趋势图留待后续）
- 不改动 Jinja2 模板侧边栏和 Jinja2 导入页
- 不实现周/月消费分析面板（数据已就绪，后续另做）
- 不支持 Excel（.xlsx）格式，仅 CSV
