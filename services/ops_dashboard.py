from datetime import datetime, timedelta

from app.models import ContentItem, Customer, FollowTask, Pet, ServiceRecord, StoreSubscription
from services.subscriptions import subscription_status_label, trial_days_left


def build_customer_opportunities(db_session, store_id: int, limit: int = 8) -> list[dict]:
    now = datetime.utcnow()
    rows = (
        db_session.query(ServiceRecord, Customer, Pet)
        .join(Customer, ServiceRecord.customer_id == Customer.id)
        .join(Pet, ServiceRecord.pet_id == Pet.id)
        .filter(ServiceRecord.store_id == store_id)
        .order_by(ServiceRecord.service_time.desc())
        .all()
    )
    latest_by_pet = {}
    for record, customer, pet in rows:
        latest_by_pet.setdefault(pet.id, (record, customer, pet))

    opportunities = []
    for record, customer, pet in latest_by_pet.values():
        if customer.do_not_disturb:
            continue
        days_since = (now - record.service_time).days
        segment = None
        action = None
        score = 0
        if days_since >= 90:
            segment = "沉睡客户"
            action = "发送沉睡唤醒关怀"
            score = 100 + days_since
        elif days_since >= pet.care_cycle_days:
            segment = "洗护到期"
            action = "发送洗护预约提醒"
            score = 50 + days_since
        elif customer.visit_count >= 3:
            segment = "高频老客"
            action = "发送会员关怀话术"
            score = 30 + customer.visit_count
        if segment is None:
            continue
        opportunities.append(
            {
                "customer_name": customer.name,
                "pet_name": pet.name,
                "segment": segment,
                "reason": f"{pet.name}距上次{record.service_type}已 {days_since} 天",
                "suggested_action": action,
                "message": _opportunity_message(customer.name, pet.name, segment),
                "score": score,
            }
        )
    opportunities.sort(key=lambda item: item["score"], reverse=True)
    return opportunities[:limit]


def build_ops_metrics(db_session, store_id: int) -> dict:
    since = datetime.utcnow() - timedelta(days=7)
    weekly_touch_tasks = (
        db_session.query(FollowTask)
        .filter(FollowTask.store_id == store_id, FollowTask.created_at >= since)
        .count()
    )
    weekly_content_items = (
        db_session.query(ContentItem)
        .filter(ContentItem.store_id == store_id, ContentItem.created_at >= since)
        .count()
    )
    monthly_repurchase_tasks = (
        db_session.query(FollowTask)
        .filter(FollowTask.store_id == store_id, FollowTask.task_type.in_(["洗护提醒", "试用装回访"]))
        .count()
    )
    avg_ticket = db_session.query(ServiceRecord.amount).filter(ServiceRecord.store_id == store_id).all()
    avg_amount = int(sum(float(row[0]) for row in avg_ticket) / len(avg_ticket)) if avg_ticket else 0
    estimated_recovered_revenue = monthly_repurchase_tasks * avg_amount
    return {
        "weekly_touch_tasks": weekly_touch_tasks,
        "weekly_content_items": weekly_content_items,
        "monthly_repurchase_customers": monthly_repurchase_tasks,
        "estimated_recovered_revenue": estimated_recovered_revenue,
    }


def build_subscription_snapshot(db_session, store_id: int) -> dict:
    subscription = (
        db_session.query(StoreSubscription)
        .filter_by(store_id=store_id)
        .order_by(StoreSubscription.created_at.desc())
        .first()
    )
    if subscription is None:
        return {
            "plan_name": "未配置",
            "status": "inactive",
            "status_label": "未配置",
            "remaining_ai_quota": 0,
            "trial_days_left": 0,
            "features": [],
        }
    status_label = subscription_status_label(subscription)
    return {
        "plan_name": subscription.plan.name,
        "status": subscription.status,
        "status_label": status_label,
        "monthly_price": subscription.plan.monthly_price,
        "remaining_ai_quota": subscription.remaining_ai_quota,
        "trial_days_left": trial_days_left(subscription),
        "trial_ends_at": subscription.trial_ends_at,
        "features": subscription.plan.features.split(",") if subscription.plan.features else [],
    }


def _opportunity_message(customer_name: str, pet_name: str, segment: str) -> str:
    if segment == "沉睡客户":
        return f"{customer_name}，好久没见{pet_name}啦，最近状态怎么样？店里可以帮您预留一次基础护理时间。"
    if segment == "洗护到期":
        return f"{customer_name}，{pet_name}上次洗护已经有一段时间啦，这周方便的话可以帮您安排一次清爽洗护。"
    return f"{customer_name}，感谢一直照顾我们小店，{pet_name}这周有需要的话我帮您优先留时间。"
