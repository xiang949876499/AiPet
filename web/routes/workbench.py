from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.dashboard import build_tiered_dashboard
from app.models import ContentItem, Customer, FollowTask, Store
from core.llm import LLMClient
from services.subscriptions import ensure_store_subscription
from web.routes.deps import get_db

router = APIRouter()

_INTERNAL_MARKETING_TERMS = (
    "高意向客户",
    "低意向客户",
    "意向客户",
    "高意向人群",
    "低意向人群",
    "意向人群",
    "客户分层",
    "客户标签",
)


def _dt(value):
    return value.isoformat() if value else None


def _empty_payload() -> dict:
    return {
        "store": {"id": None, "name": "未配置门店"},
        "metrics": {"customers": 0, "pending_tasks": 0},
        "ops_metrics": {
            "weekly_touch_tasks": 0,
            "weekly_content_items": 0,
            "monthly_repurchase_customers": 0,
            "estimated_recovered_revenue": 0,
        },
        "subscription": {
            "plan_name": "未配置",
            "status_label": "未配置",
            "credit_used": 0,
            "credit_total": 0,
            "credit_remaining": 0,
            "credit_usage_label": "本月已用 0 / 0 Credit",
            "features": [],
        },
        "ai_metrics": {},
        "conversion_funnel": None,
        "opportunities": [],
        "action_recommendations": [],
        "reminders": [],
        "content_items": [],
        "quick_actions": _quick_actions(0),
    }


def _quick_actions(pending_tasks: int) -> list[dict]:
    return [
        {
            "title": "待跟进客户",
            "description": "处理今日复购、洗护和驱虫提醒",
            "href": "/outreach",
            "tone": "red",
            "count": pending_tasks,
        },
        {
            "title": "内容活动",
            "description": "生成朋友圈、小红书和抖音素材",
            "href": "/content/calendar",
            "tone": "amber",
            "count": 2,
        },
        {
            "title": "点评口碑",
            "description": "生成差评安抚与好评回复话术",
            "href": "/review",
            "tone": "blue",
            "count": 1,
        },
        {
            "title": "AI 经营顾问",
            "description": "问经营、营销和客户沟通问题",
            "href": "/advisor",
            "tone": "green",
            "count": None,
        },
    ]


def _text(payload: dict, key: str, fallback: str = "") -> str:
    return str(payload.get(key) or fallback).strip()


def _public_marketing_copy(value: str) -> str:
    copy = value
    for term in _INTERNAL_MARKETING_TERMS:
        copy = copy.replace(term, "宠物家长")
    return copy


def _marketing_copy_prompt(payload: dict, store_name: str) -> str:
    output_type = _text(payload, "output_type", "朋友圈发布文案")
    return "\n".join(
        [
            "你是宠物门店的新媒体运营助手，只负责生成活动/内容文案，不回答经营问答。",
            f"请生成一段「{output_type}」，要求可直接复制发布。",
            "要求：",
            "- 围绕目标人群、优惠方向、推荐渠道和今天动作写具体内容",
            "- 语气自然、亲切，像真实门店发布，不要写成咨询报告",
            "- 不做医疗诊断，不承诺治疗效果，不制造焦虑",
            "- 对外文案不得出现意向客户、高意向客户、低意向客户、客户分层等内部运营术语；改用宠物家长、老朋友等自然称呼，或直接省略标签",
            "- 如果是朋友圈/小红书文案，输出标题和正文；如果是私聊触达，输出一段可直接发给客户的话术",
            "",
            f"门店：{store_name}",
            f"活动方向：{_text(payload, 'title', '老客复购唤醒')}",
            f"目标：{_text(payload, 'goal')}",
            f"目标人群：{_public_marketing_copy(_text(payload, 'target'))}",
            f"优惠方向：{_text(payload, 'offer')}",
            f"推荐渠道：{_text(payload, 'channel')}",
            f"当前动作：{_text(payload, 'action')}",
            f"参考信息：{_text(payload, 'sample')}",
        ]
    )


def _fallback_marketing_copy(payload: dict, store_name: str) -> str:
    output_type = _text(payload, "output_type", "朋友圈发布文案")
    title = _text(payload, "title", "老客复购唤醒")
    target = _public_marketing_copy(_text(payload, "target", "近期需要洗护或复购的老客"))
    offer = _text(payload, "offer", "本周护理预约权益")
    channel = _text(payload, "channel", "朋友圈")
    action = _text(payload, "action", "提醒客户预约合适时间")

    if "私聊" in output_type or "话术" in output_type:
        return (
            f"您好，这周我们给{target}准备了{offer}。如果毛孩子近期需要洗护或补充用品，"
            "可以先帮您看一下合适时间和适合项目，您看今天或明天方便吗？"
        )
    if "方案" in output_type:
        return (
            f"活动主题：{title}\n"
            f"目标人群：{target}\n"
            f"推荐渠道：{channel}\n"
            f"活动卖点：{offer}\n"
            f"今天动作：{action}\n"
            "执行建议：先发布一条预热内容，再筛选高意向客户做一对一触达，发布后回到工作台标记发布状态。"
        )
    return (
        f"标题：{title}｜本周护理提醒\n"
        f"正文：这周我们为{target}准备了{offer}。如果毛孩子最近到了洗护、护理或用品补充周期，"
        f"可以提前预约，我们会根据实际情况帮您安排合适项目。{action}，名额按预约时间安排。"
    )


def _diagnosis_prompt(payload: dict, store_name: str) -> str:
    return "\n".join(
        [
            "你是宠物门店经营诊断助手，只分析客户触达、复购、内容运营和门店动作。",
            "请输出结构化建议，不要只给一段客户话术。",
            "要求：包含优先判断、今天动作、可复制话术；不做医疗诊断，不建议用药。",
            "",
            f"门店：{store_name}",
            f"相关宠物或客户：{_text(payload, 'pet_name', '未填写')}",
            f"当前情况：{_text(payload, 'context', '未填写')}",
        ]
    )


def _fallback_diagnosis(payload: dict) -> str:
    subject = _text(payload, "pet_name", "这位客户")
    context = _text(payload, "context", "近期没有明确预约记录")
    return (
        f"优先判断：{subject}当前更适合做温和复购触达，重点确认是否需要洗护、护理或用品补充，不做医疗判断。\n"
        f"今天动作：根据当前情况「{context}」，先发一条低压力提醒；客户回复后再推荐基础洗护或合适时段。\n"
        "可复制话术：您好，想和您确认一下毛孩子最近的状态。如果这两天方便，可以先帮您看一个合适的洗护时间，"
        "到店后我们再根据实际情况建议是否需要加项。"
    )


@router.post("/marketing-copy")
def generate_marketing_copy(payload: dict, db: Session = Depends(get_db)) -> dict:
    store = db.query(Store).order_by(Store.id.asc()).first()
    store_name = store.name if store else "本店"
    prompt = _marketing_copy_prompt(payload, store_name)
    generated = LLMClient().generate(prompt)
    body = _public_marketing_copy((generated or "").strip() or _fallback_marketing_copy(payload, store_name))
    output_type = _text(payload, "output_type", "朋友圈发布文案")
    title = _text(payload, "title", "营销内容")
    return {
        "title": f"{title} · {output_type}",
        "channel": _text(payload, "channel", "朋友圈"),
        "body": body,
    }


@router.post("/diagnosis")
def generate_workbench_diagnosis(payload: dict, db: Session = Depends(get_db)) -> dict:
    store = db.query(Store).order_by(Store.id.asc()).first()
    store_name = store.name if store else "本店"
    prompt = _diagnosis_prompt(payload, store_name)
    generated = LLMClient().generate(prompt)
    answer = (generated or "").strip() or _fallback_diagnosis(payload)
    return {"answer": answer}


@router.get("")
def get_workbench(db: Session = Depends(get_db)) -> dict:
    store = db.query(Store).order_by(Store.id.asc()).first()
    if store is None:
        return _empty_payload()

    subscription = ensure_store_subscription(db, store.id)
    plan_code = subscription.plan.code if subscription.plan else "starter"
    dashboard = build_tiered_dashboard(db, store.id, plan_code)
    pending_tasks = db.query(FollowTask).filter_by(status="待处理").count()
    metrics = {
        "customers": db.query(Customer).count(),
        "pending_tasks": pending_tasks,
    }
    reminders = (
        db.query(FollowTask)
        .order_by(FollowTask.created_at.desc(), FollowTask.id.desc())
        .limit(6)
        .all()
    )
    content_items = (
        db.query(ContentItem)
        .filter_by(store_id=store.id)
        .order_by(ContentItem.scheduled_at.asc().nullslast(), ContentItem.created_at.desc())
        .limit(6)
        .all()
    )
    return {
        "store": {"id": store.id, "name": store.name},
        "metrics": metrics,
        "ops_metrics": dashboard["ops_metrics"],
        "subscription": dashboard["subscription"],
        "ai_metrics": dashboard["metrics"],
        "conversion_funnel": dashboard.get("conversion_funnel"),
        "opportunities": dashboard["opportunities"],
        "action_recommendations": dashboard["action_recommendations"],
        "reminders": [
            {
                "id": task.id,
                "customer_id": task.customer_id,
                "customer_name": task.customer.name if task.customer else "",
                "customer_phone": task.customer.phone if task.customer else None,
                "customer_wechat_name": task.customer.wechat_name if task.customer else None,
                "customer_source": task.customer.source if task.customer else None,
                "customer_tags": task.customer.tags if task.customer else None,
                "last_visit_time": _dt(task.customer.last_visit_time) if task.customer else None,
                "visit_count": task.customer.visit_count if task.customer else 0,
                "total_amount": float(task.customer.total_amount or 0) if task.customer else 0,
                "customer_do_not_disturb": bool(task.customer.do_not_disturb) if task.customer else False,
                "pet_id": task.pet_id,
                "pet_name": task.pet.name if task.pet else "",
                "pet_type": task.pet.pet_type if task.pet else None,
                "pet_breed": task.pet.breed if task.pet else None,
                "pet_character_tags": task.pet.character_tags if task.pet else None,
                "pet_care_cycle_days": task.pet.care_cycle_days if task.pet else None,
                "task_type": task.task_type,
                "priority": task.priority,
                "reason": task.reason,
                "suggested_action": task.suggested_action,
                "due_date": _dt(task.due_date),
                "status": task.status,
                "ai_message": task.ai_message,
            }
            for task in reminders
        ],
        "content_items": [
            {
                "id": item.id,
                "channel": item.channel,
                "topic": item.topic,
                "title": item.title,
                "body": item.body,
                "status": item.status,
                "scheduled_at": _dt(item.scheduled_at),
                "created_at": _dt(item.created_at),
            }
            for item in content_items
        ],
        "quick_actions": _quick_actions(pending_tasks),
    }
