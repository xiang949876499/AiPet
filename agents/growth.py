from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from agents.base import BaseAgent
from app.models import ContentItem, Customer, FollowTask, OutreachLog, ServiceRecord, Store
from core.llm import LLMClient


class StoreAuditAgent(BaseAgent):
    """Generate a lightweight marketing audit report from store and customer data."""

    def __init__(self, db_session: Session, llm: LLMClient | None = None):
        super().__init__(db_session, llm)

    def execute(self, context: dict) -> dict:
        store = _get_store(self.db_session, context.get("store_id"))
        store_name = str(context.get("store_name") or (store.name if store else "本店")).strip()
        city = str(context.get("city") or "本地").strip()
        district = str(context.get("district") or "社区商圈").strip()
        services = str(context.get("services") or "洗护, 零售").strip()
        avg_order_value = str(context.get("avg_order_value") or _average_order_value(self.db_session)).strip()
        dormant_count = _dormant_customer_count(self.db_session, store.id if store else None)

        fallback = (
            f"# {store_name} · 门店营销体检报告\n\n"
            f"定位诊断：{city}{district}的社区型宠物服务门店，适合主推“精细化洗护 + 老客会员复购”路线。\n\n"
            f"套餐诊断：当前主营服务为{services}，客单价约 {avg_order_value} 元。建议设置一个低门槛体验套餐，再用护理升级和会员权益承接。\n\n"
            "点评诊断：公开评价内容应突出“干净、温柔、不应激、准时交付”等能降低首次到店顾虑的关键词。\n\n"
            "内容诊断：朋友圈、小红书和短视频内容优先展示真实到店案例、护理前后对比和客户好评，不建议全自动发帖。\n\n"
            f"复购诊断：检测到 {dormant_count} 位客户超过 45 天未到店，建议立即启动老客召回。\n\n"
            "7 天行动清单：\n"
            "周一：筛选 45 天未到店洗护客户并生成召回话术。\n"
            "周二：发布周中错峰洗护活动内容。\n"
            "周三：邀请近期满意客户补充真实好评。\n"
            "周四：跟进已回复客户并记录到店结果。\n"
            "周五：复盘触达数、回复数、到店数和预计挽回收入。"
        )
        prompt = (
            "你是宠物店营销体检顾问。基于输入生成结构化诊断报告，"
            "包含定位诊断、套餐诊断、点评诊断、内容诊断、复购诊断、7天行动清单。"
            "不要包含医疗诊断、自动发帖或自动私信承诺。"
            f"\n门店：{store_name}\n城市：{city}\n商圈：{district}\n主营：{services}\n客单价：{avg_order_value}\n沉睡客户：{dormant_count}"
        )
        return {"report": self.render_or_fallback(prompt, fallback)}


class ActivityPlanAgent(BaseAgent):
    """Generate a manual-review campaign plan for local pet-store marketing."""

    def __init__(self, db_session: Session, llm: LLMClient | None = None):
        super().__init__(db_session, llm)

    def execute(self, context: dict) -> dict:
        activity_type = str(context.get("activity_type") or "老客复购").strip()
        target = str(context.get("target") or "45 天未到店客户").strip()
        offer = str(context.get("offer") or "基础洗护 9 折").strip()
        duration = str(context.get("duration") or "7 天").strip()
        fallback = (
            f"活动主题：{activity_type} · {target}专属护理回归计划\n\n"
            f"活动规则：活动持续 {duration}，目标客户到店可享 {offer}。需要人工确认客户名单后触达。\n\n"
            "宣传文案：\n"
            "1. 最近天气闷热，毛孩子洗护周期别拖太久，老朋友回来做护理可享专属优惠。\n"
            "2. 这周给长期未到店的毛孩子安排一次清爽洗护，提前预约更好排时间。\n"
            "3. 老客专属护理福利上线，名额有限，适合需要换季护理的毛孩子。\n\n"
            "预计效果：优先唤醒高客单老客，提升周中到店率，并沉淀可复用的内容素材。"
        )
        prompt = (
            "你是宠物店活动策划助手。生成活动主题、规则、3条宣传文案和预计效果。"
            "不要自动群发，不要承诺医疗效果。"
            f"\n类型：{activity_type}\n目标客户：{target}\n优惠：{offer}\n周期：{duration}"
        )
        return {"plan": self.render_or_fallback(prompt, fallback)}


class WeeklyReportAgent(BaseAgent):
    """Summarize weekly AI operating impact and next actions."""

    def __init__(self, db_session: Session, llm: LLMClient | None = None):
        super().__init__(db_session, llm)

    def execute(self, context: dict) -> dict:
        store = _get_store(self.db_session, context.get("store_id"))
        store_id = store.id if store else None
        since = datetime.utcnow() - timedelta(days=7)
        outreach_count = _count_recent(self.db_session, OutreachLog, store_id, since)
        reply_count = (
            self.db_session.query(OutreachLog)
            .filter(OutreachLog.created_at >= since)
            .filter(OutreachLog.response_time.isnot(None))
            .filter(OutreachLog.store_id == store_id if store_id else True)
            .count()
        )
        visit_count = (
            self.db_session.query(ServiceRecord)
            .filter(ServiceRecord.service_time >= since)
            .filter(ServiceRecord.store_id == store_id if store_id else True)
            .count()
        )
        recovered = _sum_decimal(
            log.attributed_revenue
            for log in self.db_session.query(OutreachLog).filter(OutreachLog.created_at >= since).all()
            if store_id is None or log.store_id == store_id
        )
        content_count = _count_recent(self.db_session, ContentItem, store_id, since)
        pending_count = (
            self.db_session.query(FollowTask)
            .filter(FollowTask.status == "待处理")
            .filter(FollowTask.store_id == store_id if store_id else True)
            .count()
        )

        fallback = (
            "每周复盘报告\n\n"
            f"本周数据：触达数 {outreach_count}，回复数 {reply_count}，到店数 {visit_count}，"
            f"内容产出 {content_count}，预计挽回收入 {recovered:.0f} 元。\n\n"
            f"本周问题：仍有 {pending_count} 条待处理任务，建议优先处理高客单和高回复率客户。\n\n"
            "下周建议：先做老客召回，再补齐内容日历；每天检查触达结果并回填到店和消费，形成可复盘闭环。"
        )
        prompt = (
            "你是宠物店经营复盘助手。请基于本周数据生成自然语言周报，"
            "必须包含触达数、回复数、到店数、预计挽回收入和下周建议。"
            f"\n触达：{outreach_count}\n回复：{reply_count}\n到店：{visit_count}\n内容：{content_count}\n预计挽回收入：{recovered:.0f}\n待处理：{pending_count}"
        )
        return {"report": self.render_or_fallback(prompt, fallback)}


class AdvisorAgent(BaseAgent):
    """Answer store-operation questions with a strict medical boundary."""

    medical_keywords = ("皮肤病", "用药", "药", "呕吐", "拉稀", "发烧", "诊断", "治疗", "疫苗反应")

    def __init__(self, db_session: Session, llm: LLMClient | None = None):
        super().__init__(db_session, llm)

    def execute(self, context: dict) -> dict:
        question = str(context.get("question") or "").strip()
        if any(keyword in question for keyword in self.medical_keywords):
            return {
                "answer": (
                    "关于狗狗的健康问题，建议您咨询专业兽医。"
                    "不过作为日常护理参考，可以先温和清洁、避免继续刺激皮肤，"
                    "同时记录症状出现时间和最近饮食/洗护变化，方便兽医判断。"
                )
            }

        fallback = (
            "可以从“过程 + 效果 + 风险降低”来回答客户。比如："
            "我们价格里包含专业护理产品、皮毛检查、吹干复查和预约后的时间保障，"
            "不是只比一次洗护价格，而是让毛孩子更舒服、家长更省心。"
        )
        prompt = (
            "你是宠物店 AI 经营顾问，只回答经营、营销、客户沟通和日常护理边界内的问题。"
            "不要做医疗诊断。"
            f"\n问题：{question}"
        )
        return {"answer": self.render_or_fallback(prompt, fallback)}


def _get_store(db_session: Session, store_id: object) -> Store | None:
    if store_id:
        return db_session.get(Store, int(store_id))
    return db_session.query(Store).order_by(Store.id.asc()).first()


def _average_order_value(db_session: Session) -> str:
    records = db_session.query(ServiceRecord).all()
    if not records:
        return "128"
    total = _sum_decimal(record.amount for record in records)
    return f"{total / len(records):.0f}"


def _dormant_customer_count(db_session: Session, store_id: int | None) -> int:
    cutoff = datetime.utcnow() - timedelta(days=45)
    query = db_session.query(Customer).filter(Customer.last_visit_time < cutoff)
    if store_id:
        query = query.filter(Customer.store_id == store_id)
    return query.count()


def _count_recent(db_session: Session, model: type, store_id: int | None, since: datetime) -> int:
    query = db_session.query(model).filter(model.created_at >= since)
    if store_id:
        query = query.filter(model.store_id == store_id)
    return query.count()


def _sum_decimal(values) -> Decimal:
    total = Decimal("0")
    for value in values:
        total += Decimal(str(value or 0))
    return total
