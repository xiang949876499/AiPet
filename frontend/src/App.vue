<script setup>
import { computed, onMounted, ref } from "vue";

const loading = ref(true);
const error = ref("");
const workbench = ref(null);
const activeView = ref("dashboard");
const advisorQuestion = ref("");
const advisorCategory = ref("客户沟通");
const advisorAnswer = ref("");
const advisorLoading = ref(false);
const advisorError = ref("");
const taskMessages = ref({});
const taskMessageLoading = ref({});
const taskMessageError = ref({});
const focusedTaskId = ref(null);
const selectedFollowUpTask = ref(null);
const customerIndex = ref([]);
const customerSearchQuery = ref("");
const customerLoading = ref(false);
const customerError = ref("");
const diagnosisPetName = ref("");
const diagnosisContext = ref("");
const diagnosisAnswer = ref("");
const diagnosisLoading = ref(false);
const diagnosisError = ref("");
const selectedCampaignId = ref("repurchase");
const marketingActionLoading = ref("");
const marketingActionNote = ref("");
const marketingGeneratedCopy = ref(null);
const contentPublishLoading = ref({});
const contentActionNote = ref({});
const outreachQueue = ref({ items: [], counts: { total: 0, pending_script: 0, ready_to_send: 0, sent_today: 0 } });
const outreachLoading = ref(false);
const outreachError = ref("");
const outreachActionNote = ref("");
const outreachActionLoading = ref({});
const editingOutreachId = ref(null);
const editingOutreachMessage = ref("");
const importPanelOpen = ref(false);
const importFile = ref(null);
const importPreview = ref(null);
const importResult = ref(null);
const importError = ref("");
const importLoading = ref(false);

const defaultWorkbench = {
  store: { name: "宠店 AI 管家" },
  metrics: { customers: 0, pending_tasks: 0 },
  ops_metrics: {
    weekly_touch_tasks: 0,
    weekly_content_items: 0,
    estimated_recovered_revenue: 0
  },
  subscription: {
    plan_name: "未配置",
    credit_remaining: 0,
    credit_usage_label: "本月已用 0 / 0 Credit"
  },
  ai_metrics: { reply_rate: 0 },
  conversion_funnel: null,
  reminders: [],
  content_items: [],
  quick_actions: []
};

const data = computed(() => workbench.value || defaultWorkbench);
const storeName = computed(() => data.value.store?.name || "宠店 AI 管家");
const pendingTasks = computed(() => data.value.metrics?.pending_tasks || 0);
const replyRate = computed(() => data.value.ai_metrics?.reply_rate || 0);
const recoveredRevenue = computed(() => data.value.ops_metrics?.estimated_recovered_revenue || 0);
const weeklyContent = computed(() => data.value.ops_metrics?.weekly_content_items || 0);
const creditLabel = computed(() => data.value.subscription?.credit_usage_label || "本月已用 0 / 0 Credit");

const funnel = computed(() => {
  const source = data.value.conversion_funnel || {};
  return [
    { label: "待触达", value: pendingTasks.value },
    { label: "已触达", value: source.sent || data.value.ops_metrics?.weekly_touch_tasks || 0 },
    { label: "已回复", value: source.replied || 0 },
    { label: "已预约", value: (source.visited || 0) + (source.visited ? 1 : 0) },
    { label: "已到店", value: source.visited || 0 }
  ];
});

const outreachItems = computed(() => outreachQueue.value.items || []);
const outreachCounts = computed(() => outreachQueue.value.counts || {});
const taskOutreachItems = computed(() => outreachItems.value.filter((item) => item.status === "待处理"));
const promotionItems = computed(() => (data.value.content_items || []).filter((item) => item.status !== "published").slice(0, 6));
const dashboardSummary = computed(() => [
  { label: "今日推荐联系", value: `${outreachCounts.value.ready_to_send || pendingTasks.value} 位`, tone: "blue" },
  { label: "待发布推广", value: `${promotionItems.value.length} 条`, tone: "green" },
  { label: "预计带回", value: `¥${recoveredRevenue.value}`, tone: "orange" }
]);
const customerHealth = computed(() => data.value.customer_health || { active: 0, dormant: 0, lost: 0 });
const approachComparisonRows = computed(() => {
  const source = data.value.approach_comparison || {};
  if (Array.isArray(source)) {
    return source;
  }
  return Object.entries(source).map(([name, count]) => ({ name, count }));
});
const advisorCopyNote = ref("");
const advisorCategories = [
  {
    icon: "💬",
    title: "客户沟通",
    summary: "价格异议、拒绝应对、满意度维护",
    questions: ["客户说洗护价格贵怎么回应", "客户说再看看怎么跟进"]
  },
  {
    icon: "📞",
    title: "老客召回",
    summary: "沉睡客户唤醒、复购提醒、回访话术",
    questions: ["45天未到店的客户怎么召回", "老客复购率低怎么办"]
  },
  {
    icon: "🎯",
    title: "活动策划",
    summary: "节日活动、会员日、新客引流",
    questions: ["周末想做一场新客引流活动怎么策划", "会员日怎么做"]
  },
  {
    icon: "📝",
    title: "内容营销",
    summary: "朋友圈、小红书、短视频文案",
    questions: ["今天朋友圈发什么内容比较好", "小红书怎么写种草文案"]
  },
  {
    icon: "💰",
    title: "定价策略",
    summary: "套餐定价、会员体系、涨价沟通",
    questions: ["洗护套餐怎么定价才有竞争力", "想涨价怎么跟老客户说"]
  },
  {
    icon: "📊",
    title: "数据分析",
    summary: "经营数据解读、客户分层、复盘",
    questions: ["本月到店率下降了怎么分析", "怎么给客户分层"]
  },
  {
    icon: "🏪",
    title: "门店管理",
    summary: "排班、库存、服务流程优化",
    questions: ["美容师排班怎么安排更高效", "洗护用品库存怎么管"]
  },
  {
    icon: "🐾",
    title: "养宠知识",
    summary: "品种护理、季节注意事项、日常养护",
    questions: ["夏天柯基掉毛厉害怎么护理", "猫咪应激怎么办"]
  }
];
const advisorPlaceholder = computed(() => {
  const samples = advisorCategories.flatMap((category) => category.questions);
  return samples[(new Date().getMinutes() + samples.length) % samples.length] || "客户说价格高怎么回应";
});
const viewTitles = {
  dashboard: "AI 运营助手",
  advisor: "经营问答百科",
  customers: "客户管理",
  marketing: "营销活动",
  tasks: "任务中心",
  reports: "数据看板",
  search: "搜索结果",
  diagnosis: "经营诊断",
  "follow-up": "单客跟进"
};
const viewStatus = {
  dashboard: "在线",
  advisor: "AI 驱动",
  customers: "客户同步",
  marketing: "内容待办",
  tasks: "今日处理",
  reports: "实时概览",
  search: "快速定位",
  diagnosis: "新建诊断",
  "follow-up": "专注处理"
};
const pageTitle = computed(() => viewTitles[activeView.value] || "AI 运营助手");
const pageStatus = computed(() => viewStatus[activeView.value] || "在线");
const opportunities = computed(() => data.value.opportunities?.slice(0, 6) || []);
const actionRecommendations = computed(() => data.value.action_recommendations?.slice(0, 4) || []);
const marketingContentItems = computed(() => data.value.content_items?.slice(0, 6) || []);
const selectedCampaign = computed(() => (
  campaignDirections.value.find((direction) => direction.id === selectedCampaignId.value) || campaignDirections.value[0]
));
const campaignDirections = computed(() => {
  const firstOpportunity = opportunities.value[0];
  const secondOpportunity = opportunities.value[1] || firstOpportunity;
  const fallbackCustomer = firstOpportunity?.customer_name || "30 天未到店老客";
  const fallbackPet = firstOpportunity?.pet_name || "重点宠物";
  return [
    {
      id: "repurchase",
      title: "老客复购唤醒",
      goal: "把本周洗护、驱虫和用品复购机会收回来",
      target: firstOpportunity
        ? `${firstOpportunity.customer_name} / ${firstOpportunity.pet_name} 等高意向客户`
        : "洗护周期接近、30 天未到店或用品即将用完的老客",
      offer: "会员日护理包、用品加购券或预约锁位权益",
      channel: "朋友圈 + 私聊触达",
      action: firstOpportunity?.suggested_action || "先生成朋友圈预热，再给重点客户发一段一对一提醒",
      sample: `主角客户：${fallbackCustomer}，宠物：${fallbackPet}`,
      tone: "orange"
    },
    {
      id: "weekday",
      title: "周中洗护填空",
      goal: "填补工作日空档，提高美容师排班利用率",
      target: "本周有空但还没预约的附近客户",
      offer: "周二到周四限定护理加项、早鸟预约或老客带新礼",
      channel: "小红书 + 朋友圈",
      action: "发布门店服务案例，按钮引导客户预约空档时段",
      sample: "适合展示洗护前后、护理过程和本周可预约时间",
      tone: "green"
    },
    {
      id: "new_customer",
      title: "新客到店引流",
      goal: "用低门槛体验活动带来新客咨询",
      target: secondOpportunity
        ? `${secondOpportunity.customer_name} 周边同类宠物家长`
        : "门店 3 公里内的新宠家长、幼宠家长",
      offer: "新客基础护理体验、首次到店礼或社群专属券",
      channel: "小红书 + 短视频脚本",
      action: "生成一条种草内容，再准备到店咨询话术",
      sample: "适合突出门店环境、护理标准和真实服务流程",
      tone: "blue"
    }
  ];
});
const reportStats = computed(() => [
  { label: "客户回复率", value: `${replyRate.value}%`, tone: "purple" },
  { label: "预计带回收入", value: `¥${recoveredRevenue.value}`, tone: "orange" },
  { label: "周内容产出", value: `${weeklyContent.value} 条`, tone: "green" },
  { label: "周触达量", value: `${data.value.ops_metrics?.weekly_touch_tasks || 0} 次`, tone: "blue" }
]);
const todayPriorityActions = computed(() => [
  {
    title: "联系今日推荐客户",
    description: `${outreachCounts.value.ready_to_send || pendingTasks.value} 位客户建议今天触达`,
    view: "tasks",
    tone: "blue"
  },
  {
    title: "发布推广内容",
    description: `${promotionItems.value.length} 条内容可复制后发布`,
    view: "tasks",
    tone: "green"
  },
  {
    title: "生成活动方案",
    description: "选择活动目标后生成方案或文案",
    view: "marketing",
    tone: "orange"
  }
]);
const normalizedCustomerSearchQuery = computed(() => customerSearchQuery.value.trim().toLowerCase());
const filteredCustomers = computed(() => {
  const term = normalizedCustomerSearchQuery.value;
  if (!term) {
    return customerIndex.value;
  }
  return customerIndex.value.filter((customer) => [
    customer.name,
    customer.phone,
    customer.wechat_name,
    customer.tags,
    ...(customer.pet_names || [])
  ].filter(Boolean).join(" ").toLowerCase().includes(term));
});

function legacyUrl(path) {
  return path;
}

function setView(view) {
  activeView.value = view;
  window.history.replaceState(null, "", view === "dashboard" ? window.location.pathname : `#${view}`);
  if (view === "customers") {
    loadCustomerIndex();
  }
  if (view === "tasks") {
    fetchOutreachQueue();
  }
}

async function loadCustomerIndex() {
  if (customerIndex.value.length) {
    return;
  }

  customerLoading.value = true;
  customerError.value = "";
  try {
    const response = await fetch("/api/customers");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    customerIndex.value = Array.isArray(payload) ? payload : [];
  } catch (caught) {
    customerError.value = `客户列表加载失败：${caught.message}`;
  } finally {
    customerLoading.value = false;
  }
}

function openTask(task) {
  if (!task?.id) {
    setView("tasks");
    return;
  }
  selectedFollowUpTask.value = task;
  focusedTaskId.value = task.id;
  setView("follow-up");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeFollowUp() {
  setView("tasks");
}

function profileTags(value) {
  return String(value || "")
    .split(/[，,]/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function formatDate(value) {
  return value ? String(value).slice(0, 10).replaceAll("-", ".") : "暂无记录";
}

function formatAmount(value) {
  return `¥${Number(value || 0).toFixed(0)}`;
}

function openOpportunity(item) {
  const task = (data.value.reminders || []).find((candidate) => (
    candidate.customer_name === item.customer_name
  ));
  if (!task) {
    focusedTaskId.value = null;
  }
  return openTask(task);
}

function startDiagnosis() {
  diagnosisError.value = "";
  diagnosisAnswer.value = "";
  setView("diagnosis");
}

async function submitDiagnosis() {
  const petName = diagnosisPetName.value.trim();
  const context = diagnosisContext.value.trim();
  if (!petName && !context) {
    diagnosisError.value = "先填写宠物、客户或你想诊断的经营问题。";
    return;
  }

  diagnosisLoading.value = true;
  diagnosisError.value = "";
  diagnosisAnswer.value = "";
  try {
    const response = await fetch("/api/workbench/diagnosis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pet_name: petName, context })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    diagnosisAnswer.value = payload.answer || "暂时没有生成诊断建议。";
  } catch (caught) {
    diagnosisError.value = `经营诊断失败：${caught.message}`;
  } finally {
    diagnosisLoading.value = false;
  }
}

function askMarketingAdvice() {
  setView("marketing");
  marketingActionNote.value = "已打开营销活动页，请选择一个活动方向生成朋友圈文案、小红书文案或触达话术。";
}

function selectCampaign(direction) {
  selectedCampaignId.value = direction.id;
  marketingActionNote.value = `已选择「${direction.title}」，可以继续生成方案或内容文案。`;
}

function buildCampaignCopyPayload(direction, outputType) {
  return {
    title: direction.title,
    goal: direction.goal,
    target: direction.target,
    offer: direction.offer,
    channel: direction.channel,
    action: direction.action,
    sample: direction.sample,
    output_type: outputType
  };
}

async function runCampaignAction(direction, outputType) {
  marketingActionLoading.value = `${direction.id}-${outputType}`;
  marketingActionNote.value = "";
  marketingGeneratedCopy.value = null;
  try {
    const response = await fetch("/api/workbench/marketing-copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildCampaignCopyPayload(direction, outputType))
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    marketingGeneratedCopy.value = payload;
    marketingActionNote.value = "已在当前营销页生成文案，可以直接复制或继续调整活动方向。";
    setView("marketing");
  } catch (caught) {
    marketingActionNote.value = `营销文案生成失败：${caught.message}`;
  } finally {
    marketingActionLoading.value = "";
  }
}

async function generateContentDrafts() {
  marketingActionLoading.value = "content-generate";
  marketingActionNote.value = "";
  try {
    const response = await fetch("/content/generate", { method: "POST" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    await loadWorkbench();
    marketingActionNote.value = "已生成新的内容草稿，请在下方草稿区检查后复制或标记发布。";
  } catch (caught) {
    marketingActionNote.value = `内容生成失败：${caught.message}`;
  } finally {
    marketingActionLoading.value = "";
  }
}

function viewCampaignCustomers(direction) {
  customerSearchQuery.value = direction.target;
  setView("customers");
}

function contentCopyText(item) {
  return [item.title, item.body].filter(Boolean).join("\n\n") || item.topic || "";
}

async function copyGeneratedMarketingCopy() {
  const copy = marketingGeneratedCopy.value;
  const text = [copy?.title, copy?.body].filter(Boolean).join("\n\n");
  if (!text) {
    marketingActionNote.value = "还没有可复制的生成文案。";
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    marketingActionNote.value = "生成文案已复制。";
  } catch {
    marketingActionNote.value = "浏览器暂时不允许复制，请手动选中文案。";
  }
}

async function copyContentItem(item) {
  const text = contentCopyText(item);
  if (!text) {
    contentActionNote.value = { ...contentActionNote.value, [item.id]: "这条内容还没有可复制的文案。" };
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    contentActionNote.value = { ...contentActionNote.value, [item.id]: "文案已复制，可以去对应平台发布。" };
  } catch {
    contentActionNote.value = { ...contentActionNote.value, [item.id]: "浏览器暂时不允许复制，请手动选中文案。" };
  }
}

async function publishContentItem(item) {
  contentPublishLoading.value = { ...contentPublishLoading.value, [item.id]: true };
  contentActionNote.value = { ...contentActionNote.value, [item.id]: "" };
  try {
    const form = new FormData();
    form.set("likes", "0");
    form.set("comments", "0");
    form.set("shares", "0");
    form.set("consultations", "0");
    const response = await fetch(`/content/${item.id}/publish`, {
      method: "POST",
      body: form
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    item.status = "published";
    contentActionNote.value = { ...contentActionNote.value, [item.id]: "已记录为已发布。" };
    await loadWorkbench();
  } catch (caught) {
    contentActionNote.value = { ...contentActionNote.value, [item.id]: `发布记录失败：${caught.message}` };
  } finally {
    contentPublishLoading.value = { ...contentPublishLoading.value, [item.id]: false };
  }
}

async function loadWorkbench() {
  loading.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/workbench");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    workbench.value = await response.json();
  } catch (caught) {
    error.value = `无法加载后端数据：${caught.message}`;
    workbench.value = defaultWorkbench;
  } finally {
    loading.value = false;
  }
}

async function fetchOutreachQueue() {
  outreachLoading.value = true;
  outreachError.value = "";
  try {
    const response = await fetch("/api/customers/outreach-queue");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    outreachQueue.value = payload;
  } catch (caught) {
    outreachError.value = `客户触达队列加载失败：${caught.message}`;
  } finally {
    outreachLoading.value = false;
  }
}

function mergeOutreachItem(payload) {
  const items = outreachQueue.value.items || [];
  const index = items.findIndex((item) => item.id === payload.id);
  if (index >= 0) {
    const nextItems = [...items];
    nextItems[index] = { ...nextItems[index], ...payload };
    outreachQueue.value = { ...outreachQueue.value, items: nextItems };
  }
  mergeReminder(payload);
}

async function generateOutreachMessage(item) {
  outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "generate" };
  outreachActionNote.value = "";
  try {
    const response = await fetch(`/api/reminders/${item.id}/friendly-message`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    mergeOutreachItem(payload);
    outreachActionNote.value = "话术已生成。";
  } catch (caught) {
    outreachActionNote.value = `话术生成失败：${caught.message}`;
  } finally {
    outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "" };
  }
}

function startEditOutreachMessage(item) {
  editingOutreachId.value = item.id;
  editingOutreachMessage.value = item.ai_message || "";
}

function cancelEditOutreachMessage() {
  editingOutreachId.value = null;
  editingOutreachMessage.value = "";
}

async function saveOutreachMessage(item) {
  outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "save" };
  outreachActionNote.value = "";
  try {
    const response = await fetch(`/api/reminders/${item.id}/update-message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: editingOutreachMessage.value })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    mergeOutreachItem(payload);
    cancelEditOutreachMessage();
    outreachActionNote.value = "话术已保存。";
  } catch (caught) {
    outreachActionNote.value = `保存失败：${caught.message}`;
  } finally {
    outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "" };
  }
}

async function copyOutreachMessage(item) {
  const message = item.ai_message || "";
  if (!message) {
    outreachActionNote.value = "还没有可复制的话术。";
    return;
  }
  try {
    await navigator.clipboard.writeText(message);
    outreachActionNote.value = "已复制。";
  } catch {
    outreachActionNote.value = "浏览器暂时不允许复制，请手动选中文案。";
  }
}

async function markOutreachSent(item) {
  outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "send" };
  outreachActionNote.value = "";
  try {
    const response = await fetch(`/api/reminders/${item.id}/send`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    mergeOutreachItem(payload);
    outreachActionNote.value = "已标记为已发送。";
    await fetchOutreachQueue();
  } catch (caught) {
    outreachActionNote.value = `状态更新失败：${caught.message}`;
  } finally {
    outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "" };
  }
}

async function skipOutreachTask(item) {
  outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "skip" };
  outreachActionNote.value = "";
  try {
    const response = await fetch(`/api/reminders/${item.id}/skip`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    mergeOutreachItem(payload);
    outreachActionNote.value = "已跳过。";
    await fetchOutreachQueue();
  } catch (caught) {
    outreachActionNote.value = `跳过失败：${caught.message}`;
  } finally {
    outreachActionLoading.value = { ...outreachActionLoading.value, [item.id]: "" };
  }
}

function openImportPanel() {
  importPanelOpen.value = true;
  importError.value = "";
}

function handleImportFile(event) {
  const file = event.target.files?.[0] || null;
  importFile.value = file;
  importPreview.value = null;
  importResult.value = null;
  importError.value = "";
}

async function previewCustomerImport() {
  if (!importFile.value) {
    importError.value = "先选择一个 CSV 文件。";
    return;
  }
  if (importFile.value.size > 10 * 1024 * 1024) {
    importError.value = "文件过大，请上传 10MB 以内的 CSV。";
    return;
  }
  importLoading.value = true;
  importError.value = "";
  const form = new FormData();
  form.set("csv_file", importFile.value);
  try {
    const response = await fetch("/api/customers/import/preview", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    importPreview.value = payload;
  } catch (caught) {
    importError.value = `预检失败：${caught.message}`;
  } finally {
    importLoading.value = false;
  }
}

async function submitCustomerImport() {
  if (!importFile.value) {
    importError.value = "先选择一个 CSV 文件。";
    return;
  }
  importLoading.value = true;
  importError.value = "";
  const form = new FormData();
  form.set("csv_file", importFile.value);
  try {
    const response = await fetch("/api/customers/import", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    importResult.value = payload;
    customerIndex.value = [];
    await loadWorkbench();
    await loadCustomerIndex();
  } catch (caught) {
    importError.value = `导入失败：${caught.message}`;
  } finally {
    importLoading.value = false;
  }
}

async function askAdvisor() {
  const question = advisorQuestion.value.trim();
  if (!question) {
    advisorError.value = "先输入一个经营、营销或客户沟通问题。";
    return;
  }

  advisorLoading.value = true;
  advisorError.value = "";
  advisorAnswer.value = "";
  advisorCopyNote.value = "";
  try {
    const response = await fetch("/api/advisor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, category: advisorCategory.value })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    advisorAnswer.value = payload.answer || "暂时没有生成回答。";
  } catch (caught) {
    advisorError.value = `AI 助手暂时不可用：${caught.message}`;
  } finally {
    advisorLoading.value = false;
  }
}

async function askAdvisorQuestion(question, category) {
  advisorCategory.value = category || advisorCategory.value;
  advisorQuestion.value = question;
  await askAdvisor();
}

async function copyAdvisorAnswer() {
  if (!advisorAnswer.value) {
    advisorCopyNote.value = "还没有可复制的回答。";
    return;
  }
  try {
    await navigator.clipboard.writeText(advisorAnswer.value);
    advisorCopyNote.value = "AI 回复已复制。";
  } catch {
    advisorCopyNote.value = "浏览器暂时不允许复制，请手动选中回答。";
  }
}

async function shareAdvisorAnswer() {
  if (!advisorAnswer.value) {
    advisorCopyNote.value = "还没有可分享的回答。";
    return;
  }
  const payload = {
    title: "经营问答百科",
    text: advisorAnswer.value
  };
  if (navigator.share) {
    try {
      await navigator.share(payload);
      advisorCopyNote.value = "已打开分享面板。";
      return;
    } catch {
      advisorCopyNote.value = "分享已取消。";
      return;
    }
  }
  await copyAdvisorAnswer();
}

function taskMessage(task) {
  return taskMessages.value[task.id] || task.ai_message || "";
}

function mergeReminder(payload) {
  const reminders = workbench.value?.reminders;
  if (!Array.isArray(reminders)) {
    return;
  }
  const index = reminders.findIndex((task) => task.id === payload.id);
  if (index >= 0) {
    reminders[index] = { ...reminders[index], ...payload };
  }
}

async function generateTaskMessage(task) {
  taskMessageLoading.value = { ...taskMessageLoading.value, [task.id]: true };
  taskMessageError.value = { ...taskMessageError.value, [task.id]: "" };
  try {
    const response = await fetch(`/api/reminders/${task.id}/friendly-message`, {
      method: "POST"
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    taskMessages.value = { ...taskMessages.value, [task.id]: payload.ai_message || "" };
    mergeReminder(payload);
  } catch (caught) {
    taskMessageError.value = {
      ...taskMessageError.value,
      [task.id]: `话术生成失败：${caught.message}`
    };
  } finally {
    taskMessageLoading.value = { ...taskMessageLoading.value, [task.id]: false };
  }
}

async function markTaskDone(task) {
  taskMessageError.value = { ...taskMessageError.value, [task.id]: "" };
  try {
    const response = await fetch(`/api/reminders/${task.id}/send`, {
      method: "POST"
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    mergeReminder(payload);
  } catch (caught) {
    taskMessageError.value = {
      ...taskMessageError.value,
      [task.id]: `状态更新失败：${caught.message}`
    };
  }
}

async function copyTaskMessage(task) {
  const message = taskMessage(task) || task.suggested_action || task.reason || "";
  if (!message) {
    taskMessageError.value = { ...taskMessageError.value, [task.id]: "还没有可复制的话术" };
    return;
  }
  try {
    await navigator.clipboard.writeText(message);
    taskMessageError.value = { ...taskMessageError.value, [task.id]: "话术已复制" };
  } catch {
    taskMessageError.value = { ...taskMessageError.value, [task.id]: "浏览器暂时不允许复制，请手动选中话术" };
  }
}

onMounted(() => {
  const initialView = window.location.hash.replace("#", "");
  if (viewTitles[initialView]) {
    activeView.value = initialView;
  }
  loadWorkbench();
  if (activeView.value === "customers") {
    loadCustomerIndex();
  }
  if (activeView.value === "tasks") {
    fetchOutreachQueue();
  }
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" aria-label="主导航">
      <div class="sidebar-logo">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="#E88262" />
          <path d="M10 20c0-4 3-7 6-7s6 3 6 7" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" />
          <circle cx="12" cy="12" r="2" fill="#fff" />
          <circle cx="20" cy="12" r="2" fill="#fff" />
          <path d="M16 16v4" stroke="#fff" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        宠店 AI 管家
      </div>

      <nav class="sidebar-nav">
        <a class="nav-item" :class="{ active: activeView === 'dashboard' }" href="#" @click.prevent="setView('dashboard')">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="2" y="2" width="7" height="8" rx="1"/><rect x="11" y="2" width="7" height="5" rx="1"/><rect x="2" y="12" width="7" height="6" rx="1"/><rect x="11" y="9" width="7" height="9" rx="1"/></svg>
          工作台
        </a>
        <a class="nav-item" :class="{ active: activeView === 'advisor' }" href="#advisor" @click.prevent='setView("advisor")'>
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10" cy="10" r="8"/><path d="M10 6v4l3 2"/></svg>
          AI 助手
        </a>
        <a class="nav-item" :class="{ active: activeView === 'customers' }" href="#customers" @click.prevent="setView('customers')">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M6.5 8.5a3 3 0 116 0 3 3 0 01-6 0z"/><path d="M3.5 17c.8-3 3.2-4.5 6.5-4.5s5.7 1.5 6.5 4.5"/></svg>
          客户管理
        </a>
        <a class="nav-item" :class="{ active: activeView === 'marketing' }" href="#marketing" @click.prevent="setView('marketing')">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 6h14"/><path d="M3 10h14"/><path d="M3 14h10"/></svg>
          营销活动
          <span class="nav-badge">2</span>
        </a>
        <a class="nav-item" :class="{ active: activeView === 'tasks' }" href="#tasks" @click.prevent="setView('tasks')">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><polygon points="10 1 13 7 20 8 15 13 16 20 10 17 4 20 5 13 0 8 7 7"/></svg>
          任务中心
          <span v-if="pendingTasks" class="nav-badge hot">{{ pendingTasks }}</span>
        </a>
        <a class="nav-item" :class="{ active: activeView === 'reports' }" href="#reports" @click.prevent="setView('reports')">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10" cy="10" r="3"/><path d="M10 1v3"/><path d="M10 16v3"/><path d="M1 10h3"/><path d="M16 10h3"/></svg>
          数据看板
        </a>
      </nav>

      <div class="quick-entry-group" aria-label="快捷入口">
        <div class="quick-entry-title">快捷入口</div>
        <div class="quick-entry-list">
          <button type="button" @click="setView('customers'); openImportPanel()">导入客户</button>
          <button type="button" @click="setView('marketing')">活动方案</button>
          <button type="button" @click="setView('advisor')">AI 顾问</button>
          <button type="button" @click="setView('reports')">授权额度</button>
        </div>
      </div>

      <div class="sidebar-bottom">
        <div class="shop-badge">
          <div class="shop-avatar">店</div>
          <div class="shop-info">
            <div class="shop-name">{{ storeName }}</div>
            <div class="shop-state">数据已同步</div>
          </div>
        </div>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <h1>{{ pageTitle }}</h1>
          <span class="btn btn-sm status-chip">{{ pageStatus }}</span>
        </div>
        <div class="topbar-actions">
          <a class="btn btn-ghost btn-sm" href="#tasks" @click.prevent="setView('tasks')">待处理 {{ pendingTasks }}</a>
          <a class="btn btn-primary btn-sm" href="#diagnosis" @click.prevent="startDiagnosis">新建诊断</a>
        </div>
      </header>

      <div class="ai-layout">
        <main class="ai-chat-area">
          <div class="ai-chat-header">
            <h2><span class="bot-mark" aria-hidden="true"></span> {{ storeName }}</h2>
            <span class="ai-status">已接入后端数据</span>
          </div>

          <div v-if="activeView === 'dashboard'" class="workbench-content">
            <div v-if="error" class="notice error">{{ error }}</div>
            <div v-else-if="loading" class="notice">正在加载门店运营数据...</div>

            <section class="metric-grid" aria-label="今日概览">
              <article v-for="item in dashboardSummary" :key="item.label" class="metric-card" :class="`accent-${item.tone}`">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <em>今日概览</em>
              </article>
            </section>

            <section class="panel-grid">
              <article class="panel list-panel">
                <header>
                  <h3>今日优先动作</h3>
                  <a href="#tasks" @click.prevent="setView('tasks')">进入任务中心</a>
                </header>
                <button
                  v-for="action in todayPriorityActions"
                  :key="action.title"
                  class="priority-action-card"
                  :class="`accent-${action.tone}`"
                  type="button"
                  @click="setView(action.view)"
                >
                  <span>
                    <strong>{{ action.title }}</strong>
                    <small>{{ action.description }}</small>
                  </span>
                  <b>去处理</b>
                </button>
              </article>

              <article class="panel list-panel">
                <header>
                  <h3>快捷入口</h3>
                  <a href="#advisor" @click.prevent="setView('advisor')">问 AI</a>
                </header>
                <div class="quick-entry-list">
                  <button type="button" @click="setView('tasks')">今日联系</button>
                  <button type="button" @click="setView('tasks')">发布推广</button>
                  <button type="button" @click="setView('customers')">客户列表</button>
                  <button type="button" @click="setView('marketing')">生成活动</button>
                  <button type="button" @click="setView('reports')">看数据</button>
                </div>
              </article>
            </section>
          </div>

          <div v-else-if="activeView === 'diagnosis'" class="workbench-content diagnosis-view">
            <section class="panel diagnosis-panel">
              <header>
                <h3>经营诊断</h3>
                <p>这里用于分析客户触达、复购、内容和门店动作，不做宠物医疗诊断。</p>
              </header>
              <form class="diagnosis-form" @submit.prevent="submitDiagnosis">
                <label>
                  <span>客户或宠物</span>
                  <input v-model="diagnosisPetName" class="ai-input" type="text" placeholder="例如：王姐 / 小七 / 柯基客户" />
                </label>
                <label>
                  <span>当前情况</span>
                  <textarea
                    v-model="diagnosisContext"
                    rows="5"
                    placeholder="例如：客户 22 天没来洗护，最近 7 天没有预约，希望生成今天可以执行的处理建议。"
                  ></textarea>
                </label>
                <div class="advisor-actions">
                  <button class="btn btn-primary" type="submit" :disabled="diagnosisLoading">
                    {{ diagnosisLoading ? "诊断中..." : "生成诊断建议" }}
                  </button>
                  <button
                    class="btn btn-ghost"
                    type="button"
                    @click="diagnosisPetName = '王姐 · 小七'; diagnosisContext = '小七上次洗护距今 22 天，最近 7 天没有预约，希望今天安排一次温和触达。'"
                  >
                    填入示例
                  </button>
                </div>
              </form>
            </section>

            <section class="panel diagnosis-result">
              <header>
                <h3>诊断建议</h3>
                <p>生成后可直接转成任务话术或活动动作。</p>
              </header>
              <div v-if="diagnosisError" class="notice error">{{ diagnosisError }}</div>
              <div v-else-if="diagnosisLoading" class="notice">正在整理诊断建议...</div>
              <div v-else-if="diagnosisAnswer" class="advisor-answer">{{ diagnosisAnswer }}</div>
              <div v-else class="advisor-empty">
                <strong>可诊断：</strong>
                <span>客户回访优先级</span>
                <span>今日触达动作</span>
                <span>复购话术</span>
                <span>内容运营方向</span>
              </div>
            </section>
          </div>

          <div v-else-if="activeView === 'advisor'" class="workbench-content advisor-view">
            <section class="advisor-search-panel">
              <div class="advisor-hero">
                <span class="advisor-kicker">AI 驱动</span>
                <h2>经营问答百科</h2>
              </div>
              <div class="advisor-search-row">
                <label class="sr-only" for="advisor-question">输入经营问题</label>
                <input
                  id="advisor-question"
                  v-model="advisorQuestion"
                  class="advisor-search-input"
                  type="search"
                  :placeholder="advisorPlaceholder"
                  @keyup.enter="askAdvisor"
                >
                <button class="btn btn-primary" type="button" :disabled="advisorLoading" @click="askAdvisor">
                  {{ advisorLoading ? "生成中..." : "提问" }}
                </button>
              </div>
            </section>

            <section class="advisor-category-grid" aria-label="经营问题分类">
              <article
                v-for="category in advisorCategories"
                :key="category.title"
                class="advisor-category-card"
                :class="{ active: advisorCategory === category.title }"
              >
                <header>
                  <span class="advisor-category-icon" aria-hidden="true">{{ category.icon }}</span>
                  <div>
                    <h3>{{ category.title }}</h3>
                    <p>{{ category.summary }}</p>
                  </div>
                </header>
                <div class="advisor-question-list">
                  <button
                    v-for="question in category.questions"
                    :key="question"
                    class="advisor-question-link"
                    type="button"
                    @click="askAdvisorQuestion(question, category.title)"
                  >
                    {{ question }}
                  </button>
                </div>
              </article>
            </section>

            <section class="panel advisor-answer-panel">
              <header class="advisor-answer-toolbar">
                <div>
                  <h3>AI 回复</h3>
                  <p>{{ advisorQuestion || "选择一个问题开始" }}</p>
                </div>
                <div class="advisor-actions">
                  <button class="task-button primary" type="button" :disabled="!advisorAnswer" @click="copyAdvisorAnswer">复制</button>
                  <button class="task-button" type="button" :disabled="!advisorAnswer" @click="shareAdvisorAnswer">分享</button>
                </div>
              </header>
              <div v-if="advisorError" class="notice error">{{ advisorError }}</div>
              <div v-else-if="advisorLoading" class="notice">正在整理回答...</div>
              <div v-else-if="advisorAnswer" class="advisor-answer">{{ advisorAnswer }}</div>
              <div v-else class="advisor-empty">
                <strong>推荐问题</strong>
                <button
                  v-for="question in advisorCategories[0].questions"
                  :key="question"
                  type="button"
                  @click="askAdvisorQuestion(question, advisorCategories[0].title)"
                >
                  {{ question }}
                </button>
              </div>
              <em v-if="advisorCopyNote" class="task-inline-note">{{ advisorCopyNote }}</em>
            </section>
          </div>

          <div v-else-if="activeView === 'customers'" class="workbench-content customers-view">
            <div class="view-action-bar">
              <button class="btn btn-primary" type="button" @click="openImportPanel">导入客户</button>
              <a class="btn btn-ghost" href="/api/customers/import/template">下载模板</a>
              <button class="btn btn-ghost" type="button" @click="customerIndex = []; loadCustomerIndex()">刷新客户</button>
            </div>

            <section v-if="importPanelOpen" class="panel import-panel">
              <header>
                <h3>导入客户数据</h3>
                <p>CSV 可包含到店日期、服务项目、消费金额和备注；预检后再确认导入。</p>
              </header>
              <label class="import-dropzone">
                <input type="file" accept=".csv,text/csv" @change="handleImportFile" />
                <span>{{ importFile ? importFile.name : "选择或拖入 CSV 文件" }}</span>
                <small>仅支持 CSV，文件不超过 10MB。</small>
              </label>
              <div class="advisor-actions">
                <button class="btn btn-primary" type="button" :disabled="importLoading" @click="previewCustomerImport">
                  {{ importLoading ? "处理中" : "预检" }}
                </button>
                <button class="btn btn-ghost" type="button" :disabled="!importPreview || importLoading" @click="submitCustomerImport">确认导入</button>
                <button class="btn btn-ghost" type="button" @click="importPanelOpen = false">收起</button>
              </div>
              <div v-if="importError" class="notice error">{{ importError }}</div>
              <div v-if="importPreview" class="import-summary-grid">
                <span><strong>{{ importPreview.total_rows }}</strong><small>总行数</small></span>
                <span><strong>{{ importPreview.ready_rows }}</strong><small>可导入</small></span>
                <span><strong>{{ importPreview.skipped_rows }}</strong><small>跳过</small></span>
                <span><strong>{{ importPreview.estimated_service_records }}</strong><small>消费记录</small></span>
                <span><strong>¥{{ importPreview.estimated_total_amount }}</strong><small>总金额</small></span>
              </div>
              <div v-if="importPreview?.issues?.length" class="import-issues">
                <div v-for="issue in importPreview.issues" :key="`${issue.row_number}-${issue.field}-${issue.message}`">
                  第 {{ issue.row_number }} 行 · {{ issue.field }}：{{ issue.message }}
                </div>
              </div>
              <div v-if="importResult" class="notice">
                导入完成：新增客户 {{ importResult.created_customers }} 位，更新 {{ importResult.updated_customers }} 位，新增宠物 {{ importResult.created_pets }} 只，消费记录 {{ importResult.created_service_records }} 条。
              </div>
            </section>

            <section class="panel feature-panel wide-panel customer-list-panel">
              <header>
                <div>
                  <h3>客户列表</h3>
                  <p>展示全部客户，搜索只在客户管理页生效。</p>
                </div>
                <label class="customer-search-field">
                  <span class="sr-only">搜索客户</span>
                  <input
                    v-model="customerSearchQuery"
                    class="customer-search-input"
                    type="search"
                    placeholder="搜索客户名 / 手机号 / 宠物名"
                  >
                </label>
              </header>
              <div v-if="customerError" class="notice error">{{ customerError }}</div>
              <div v-else-if="customerLoading" class="notice">正在加载客户列表...</div>
              <div v-else-if="!filteredCustomers.length" class="empty">没有找到匹配客户</div>
              <div v-for="customer in filteredCustomers" :key="customer.id" class="customer-row">
                <div class="customer-main">
                  <strong>{{ customer.name || "未知客户" }}</strong>
                  <small>{{ [customer.phone, customer.wechat_name, (customer.pet_names || []).join("、")].filter(Boolean).join(" · ") || "客户档案待完善" }}</small>
                </div>
                <div class="customer-stats">
                  <span>{{ customer.visit_count || 0 }} 次到店</span>
                  <b>{{ formatAmount(customer.total_amount) }}</b>
                </div>
              </div>
            </section>
          </div>

          <div v-else-if="activeView === 'marketing'" class="workbench-content marketing-view">
            <section class="panel marketing-step">
              <header>
                <span class="step-kicker">第一步</span>
                <div>
                  <h3>选择活动目标</h3>
                  <p>先确定本次营销要解决的目标，再生成方案或文案。</p>
                </div>
              </header>
              <div class="campaign-direction-grid" aria-label="营销活动方向">
                <article
                  v-for="direction in campaignDirections"
                  :key="direction.id"
                  class="campaign-card"
                  :class="[`campaign-${direction.tone}`, { active: selectedCampaignId === direction.id }]"
                >
                  <header>
                    <span class="campaign-kicker">{{ direction.channel }}</span>
                    <h3>{{ direction.title }}</h3>
                    <p>{{ direction.goal }}</p>
                  </header>
                  <dl class="campaign-facts">
                    <div>
                      <dt>目标人群</dt>
                      <dd>{{ direction.target }}</dd>
                    </div>
                    <div>
                      <dt>活动卖点</dt>
                      <dd>{{ direction.offer }}</dd>
                    </div>
                    <div>
                      <dt>今天动作</dt>
                      <dd>{{ direction.action }}</dd>
                    </div>
                  </dl>
                  <div class="campaign-actions">
                    <button class="task-button primary" type="button" @click="selectCampaign(direction)">设为主推</button>
                    <button class="task-button" type="button" @click="viewCampaignCustomers(direction)">查看目标客户</button>
                  </div>
                </article>
              </div>
            </section>

            <section class="panel marketing-step">
              <header>
                <span class="step-kicker">第二步</span>
                <div>
                  <h3>生成方案 / 文案</h3>
                  <p>当前目标：{{ selectedCampaign.title }} · {{ selectedCampaign.goal }}</p>
                </div>
              </header>
              <div class="campaign-actions">
                <button class="btn btn-primary" type="button" @click="runCampaignAction(selectedCampaign, '完整活动方案')">生成活动方案</button>
                <button class="btn btn-ghost" type="button" @click="runCampaignAction(selectedCampaign, '朋友圈发布文案')">朋友圈文案</button>
                <button class="btn btn-ghost" type="button" @click="runCampaignAction(selectedCampaign, '小红书种草文案')">小红书文案</button>
                <button class="btn btn-ghost" type="button" @click="runCampaignAction(selectedCampaign, '客户私聊触达话术')">触达话术</button>
                <button class="btn btn-ghost" type="button" :disabled="marketingActionLoading === 'content-generate'" @click="generateContentDrafts">
                  {{ marketingActionLoading === "content-generate" ? "生成中" : "生成内容草稿" }}
                </button>
              </div>
            </section>
            <div v-if="marketingActionNote" class="notice">{{ marketingActionNote }}</div>
            <section v-if="marketingGeneratedCopy" class="panel feature-panel wide-panel generated-copy-panel">
              <header>
                <h3>{{ marketingGeneratedCopy.title || "生成文案" }}</h3>
                <p>{{ marketingGeneratedCopy.channel || "营销内容" }}</p>
              </header>
              <div class="advisor-answer">{{ marketingGeneratedCopy.body }}</div>
              <div class="advisor-actions">
                <button class="btn btn-primary" type="button" @click="copyGeneratedMarketingCopy">复制生成文案</button>
                <button class="btn btn-ghost" type="button" @click="marketingGeneratedCopy = null">收起</button>
              </div>
            </section>

            <section class="panel marketing-step">
              <header>
                <span class="step-kicker">第三步</span>
                <div>
                  <h3>查看内容草稿</h3>
                  <p>这里仅检查和复制草稿；发布执行放到任务中心。</p>
                </div>
              </header>
              <article class="feature-panel wide-panel">
                <header>
                  <h3>内容草稿</h3>
                  <p>确认文案是否可用，复制后去任务中心标记发布。</p>
                </header>
                <div v-if="!marketingContentItems.length" class="empty">暂无内容草稿，点击上方“生成内容草稿”开始。</div>
                <div v-for="item in marketingContentItems" :key="item.id" class="content-publish-row">
                  <div class="content-copy">
                    <strong>{{ item.title || item.topic || "内容草稿" }}</strong>
                    <small>{{ item.channel || "渠道" }} · {{ item.topic || "待定主题" }} · {{ item.status || "草稿" }}</small>
                    <p>{{ item.body || "这条内容还没有正文，先生成草稿或去旧版内容日历补充。" }}</p>
                    <em v-if="contentActionNote[item.id]">{{ contentActionNote[item.id] }}</em>
                  </div>
                  <div class="content-actions">
                    <button class="task-button primary" type="button" @click="copyContentItem(item)">复制文案</button>
                    <button class="task-button" type="button" @click="setView('tasks')">去任务中心发布</button>
                  </div>
                </div>
              </article>
            </section>
          </div>

          <div v-else-if="activeView === 'follow-up'" class="workbench-content follow-up-view">
            <section v-if="selectedFollowUpTask" class="follow-up-header">
              <div class="follow-up-identity">
                <span class="follow-up-kicker">待跟进客户</span>
                <div class="follow-up-title-row">
                  <h2>{{ selectedFollowUpTask.customer_name || "未知客户" }}</h2>
                  <span class="task-status-pill">{{ selectedFollowUpTask.status }}</span>
                </div>
                <p>{{ selectedFollowUpTask.pet_name || "宠物" }} · {{ selectedFollowUpTask.task_type || "客户跟进" }}</p>
              </div>
              <button class="btn btn-ghost" type="button" @click="closeFollowUp">返回任务列表</button>
            </section>

            <section v-if="selectedFollowUpTask" class="follow-up-grid">
              <article class="follow-up-profile">
                <header>
                  <h3>客户资料</h3>
                  <span>{{ selectedFollowUpTask.customer_source || "门店客户" }}</span>
                </header>
                <dl class="profile-facts">
                  <div>
                    <dt>联系电话</dt>
                    <dd>{{ selectedFollowUpTask.customer_phone || "未填写" }}</dd>
                  </div>
                  <div>
                    <dt>微信昵称</dt>
                    <dd>{{ selectedFollowUpTask.customer_wechat_name || "未填写" }}</dd>
                  </div>
                  <div>
                    <dt>最近到店</dt>
                    <dd>{{ formatDate(selectedFollowUpTask.last_visit_time) }}</dd>
                  </div>
                  <div>
                    <dt>到店次数</dt>
                    <dd>{{ selectedFollowUpTask.visit_count || 0 }} 次</dd>
                  </div>
                  <div>
                    <dt>累计消费</dt>
                    <dd>{{ formatAmount(selectedFollowUpTask.total_amount) }}</dd>
                  </div>
                  <div>
                    <dt>联系状态</dt>
                    <dd>{{ selectedFollowUpTask.customer_do_not_disturb ? "暂不打扰" : "可联系" }}</dd>
                  </div>
                </dl>
                <div v-if="profileTags(selectedFollowUpTask.customer_tags).length" class="profile-tags" aria-label="客户标签">
                  <span v-for="tag in profileTags(selectedFollowUpTask.customer_tags)" :key="tag">{{ tag }}</span>
                </div>

                <div class="pet-profile">
                  <span>宠物资料</span>
                  <strong>{{ selectedFollowUpTask.pet_name || "宠物" }}</strong>
                  <small>{{ [selectedFollowUpTask.pet_type, selectedFollowUpTask.pet_breed].filter(Boolean).join(" · ") || "宠物信息待补充" }}</small>
                  <small v-if="selectedFollowUpTask.pet_care_cycle_days">建议护理周期：{{ selectedFollowUpTask.pet_care_cycle_days }} 天</small>
                  <div v-if="profileTags(selectedFollowUpTask.pet_character_tags).length" class="profile-tags">
                    <span v-for="tag in profileTags(selectedFollowUpTask.pet_character_tags)" :key="tag">{{ tag }}</span>
                  </div>
                </div>
              </article>

              <article class="follow-up-action">
                <header>
                  <div>
                    <span class="follow-up-kicker">本次跟进</span>
                    <h3>{{ selectedFollowUpTask.reason }}</h3>
                  </div>
                  <span class="priority-chip">{{ selectedFollowUpTask.priority || "普通" }}</span>
                </header>
                <div class="follow-up-step">
                  <span>建议动作</span>
                  <p>{{ selectedFollowUpTask.suggested_action || "先确认客户近期需求，再安排下一步服务。" }}</p>
                </div>
                <div class="follow-up-message">
                  <span>推荐话术</span>
                  <p>{{ taskMessage(selectedFollowUpTask) || "先生成一段亲切话术，再复制给客户。" }}</p>
                </div>
                <em v-if="taskMessageError[selectedFollowUpTask.id]" class="task-inline-note">{{ taskMessageError[selectedFollowUpTask.id] }}</em>
                <div class="follow-up-actions">
                  <button
                    class="btn btn-primary"
                    type="button"
                    :disabled="taskMessageLoading[selectedFollowUpTask.id]"
                    @click="generateTaskMessage(selectedFollowUpTask)"
                  >
                    {{ taskMessageLoading[selectedFollowUpTask.id] ? "生成中" : "生成亲切话术" }}
                  </button>
                  <button class="btn btn-ghost" type="button" @click="copyTaskMessage(selectedFollowUpTask)">复制话术</button>
                  <button class="btn btn-ghost" type="button" @click="markTaskDone(selectedFollowUpTask)">标记已处理</button>
                </div>
              </article>
            </section>

            <section v-else class="empty">
              请从任务列表选择一位客户开始跟进。
            </section>
          </div>

          <div v-else-if="activeView === 'tasks'" class="workbench-content tasks-view">
            <div class="view-action-bar">
              <button class="btn btn-primary" type="button" @click="fetchOutreachQueue">刷新今日任务</button>
              <button class="btn btn-ghost" type="button" @click="setView('reports')">查看数据</button>
              <button class="btn btn-ghost" type="button" @click="setView('marketing')">生成内容</button>
            </div>

            <section class="task-center-grid">
              <article class="panel feature-panel recommended-customer-column">
                <header>
                  <h3>推荐今日联系的客户</h3>
                  <p>根据待办和机会合并成唯一触达入口。</p>
                </header>
                <div v-if="outreachError" class="notice error">{{ outreachError }}</div>
                <div v-else-if="outreachLoading" class="notice">正在加载今日推荐客户...</div>
                <div v-else-if="!taskOutreachItems.length" class="empty">暂无推荐联系客户</div>
                <div v-for="item in taskOutreachItems" :key="item.id" class="outreach-item">
                  <div class="outreach-item-head">
                    <span>
                      <strong>{{ item.customer_name || "未知客户" }} · {{ item.pet_name || "宠物" }}</strong>
                      <small>{{ item.reason }} · {{ item.suggested_action }}</small>
                    </span>
                    <b>{{ item.priority || item.status }}</b>
                  </div>
                  <div class="outreach-message-box">
                    <textarea v-if="editingOutreachId === item.id" v-model="editingOutreachMessage" rows="4"></textarea>
                    <p v-else>{{ item.ai_message || "还没有话术，先生成一段可发送给客户的微信话术。" }}</p>
                    <button v-if="item.ai_message && editingOutreachId !== item.id" class="task-button" type="button" @click="startEditOutreachMessage(item)">编辑</button>
                  </div>
                  <div class="outreach-actions">
                    <template v-if="editingOutreachId === item.id">
                      <button class="task-button primary" type="button" :disabled="outreachActionLoading[item.id] === 'save'" @click="saveOutreachMessage(item)">保存</button>
                      <button class="task-button" type="button" @click="cancelEditOutreachMessage">取消</button>
                    </template>
                    <template v-else-if="item.ai_message">
                      <button class="task-button" type="button" :disabled="outreachActionLoading[item.id] === 'generate'" @click="generateOutreachMessage(item)">重新生成</button>
                      <button class="task-button" type="button" @click="copyOutreachMessage(item)">复制话术</button>
                      <button class="task-button primary" type="button" :disabled="outreachActionLoading[item.id] === 'send'" @click="markOutreachSent(item)">标记已发送</button>
                      <button class="task-button" type="button" :disabled="outreachActionLoading[item.id] === 'skip'" @click="skipOutreachTask(item)">跳过</button>
                    </template>
                    <template v-else>
                      <button class="task-button primary" type="button" :disabled="outreachActionLoading[item.id] === 'generate'" @click="generateOutreachMessage(item)">生成话术</button>
                      <button class="task-button" type="button" :disabled="outreachActionLoading[item.id] === 'skip'" @click="skipOutreachTask(item)">跳过</button>
                    </template>
                  </div>
                  <em v-if="outreachActionNote" class="task-inline-note">{{ outreachActionNote }}</em>
                </div>
              </article>

              <article class="panel feature-panel promotion-publish-column">
                <header>
                  <h3>待发布推广内容</h3>
                  <p>复制文案到对应平台发布，再回到这里标记发布。</p>
                </header>
                <div v-if="!promotionItems.length" class="empty">暂无待发布推广内容</div>
                <div v-for="item in promotionItems" :key="item.id" class="promotion-item">
                  <div class="content-copy">
                    <strong>{{ item.title || item.topic || "推广内容" }}</strong>
                    <small>{{ item.channel || "渠道" }} · {{ item.topic || "待定主题" }} · {{ item.status || "草稿" }}</small>
                    <p>{{ item.body || "这条内容还没有正文，请先到营销活动生成草稿。" }}</p>
                    <em v-if="contentActionNote[item.id]">{{ contentActionNote[item.id] }}</em>
                  </div>
                  <div class="content-actions">
                    <button class="task-button primary" type="button" @click="copyContentItem(item)">复制文案</button>
                    <button class="task-button" type="button" :disabled="contentPublishLoading[item.id]" @click="publishContentItem(item)">
                      {{ contentPublishLoading[item.id] ? "记录中" : "标记已发布" }}
                    </button>
                  </div>
                </div>
              </article>
            </section>
          </div>

          <div v-else-if="activeView === 'reports'" class="workbench-content reports-view">
            <div class="view-action-bar">
              <button class="btn btn-primary" type="button" @click="loadWorkbench">刷新数据</button>
              <button class="btn btn-ghost" type="button" @click="setView('tasks')">转到任务</button>
              <button class="btn btn-ghost" type="button" @click="askMarketingAdvice">问营销建议</button>
            </div>

            <section class="metric-grid">
              <article v-for="stat in reportStats" :key="stat.label" class="metric-card" :class="`accent-${stat.tone}`">
                <span>{{ stat.label }}</span>
                <strong>{{ stat.value }}</strong>
                <em>来自实时工作台数据</em>
              </article>
            </section>
            <section class="view-grid">
              <article class="panel feature-panel">
                <header>
                  <h3>经营漏斗</h3>
                  <p>触达、回复、预约和到店的转化链路。</p>
                </header>
                <div class="mini-funnel">
                  <span v-for="step in funnel" :key="step.label">
                    <strong>{{ step.value }}</strong>
                    <small>{{ step.label }}</small>
                  </span>
                </div>
              </article>
              <article class="panel feature-panel">
                <header>
                  <h3>客户健康</h3>
                  <p>活跃、沉睡和流失客户分布。</p>
                </header>
                <div class="mini-funnel">
                  <span>
                    <strong>{{ customerHealth.active || 0 }}</strong>
                    <small>活跃</small>
                  </span>
                  <span>
                    <strong>{{ customerHealth.dormant || 0 }}</strong>
                    <small>沉睡</small>
                  </span>
                  <span>
                    <strong>{{ customerHealth.lost || 0 }}</strong>
                    <small>流失</small>
                  </span>
                </div>
              </article>
              <article class="panel feature-panel">
                <header>
                  <h3>触达策略效果</h3>
                  <p>对比不同策略的触达量。</p>
                </header>
                <div v-if="!approachComparisonRows.length" class="empty">暂无策略对比数据</div>
                <div v-for="item in approachComparisonRows" :key="item.name || item.strategy" class="diag-row">
                  <span>{{ item.name || item.strategy || "触达策略" }}</span>
                  <b class="diag-val">{{ item.count || item.value || 0 }}</b>
                </div>
              </article>
              <article class="panel feature-panel">
                <header>
                  <h3>数据摘要</h3>
                  <p>快速判断今天先处理哪一类问题。</p>
                </header>
                <div class="advisor-answer">
                  目前回复率 {{ replyRate }}%，预计带回收入 ¥{{ recoveredRevenue }}，月到店与周营收可继续结合消费记录完善。数据看板只保留经营结果，不展示待办执行列表。
                </div>
              </article>
            </section>
          </div>
        </main>

      </div>
    </div>
  </div>
</template>
