from datetime import datetime, timedelta

from app.models import Store, StoreSubscription, SubscriptionPlan


DEFAULT_PLANS = [
    {
        "code": "experience",
        "name": "体验版",
        "monthly_price": 19,
        "annual_price": 190,
        "ai_quota_monthly": 100,
        "features": "轻度试用,点评回复,基础内容生成",
        "is_recommended": False,
    },
    {
        "code": "starter",
        "name": "入门版",
        "monthly_price": 199,
        "annual_price": 1990,
        "ai_quota_monthly": 500,
        "features": "客户提醒,基础话术,手动复制发送,内容草稿",
        "is_recommended": False,
    },
    {
        "code": "professional",
        "name": "专业版",
        "monthly_price": 499,
        "annual_price": 4990,
        "ai_quota_monthly": 1500,
        "features": "企业微信,内容日历,客户分层,复购追踪,活动方案",
        "is_recommended": True,
    },
    {
        "code": "growth",
        "name": "增长版",
        "monthly_price": 999,
        "annual_price": 9990,
        "ai_quota_monthly": 3000,
        "features": "活动Agent,自媒体批量生成,周报,体检报告",
        "is_recommended": False,
    },
]


def seed_subscription_plans(db_session) -> list[SubscriptionPlan]:
    plans: list[SubscriptionPlan] = []
    for data in DEFAULT_PLANS:
        plan = db_session.query(SubscriptionPlan).filter_by(code=data["code"]).one_or_none()
        if plan is None:
            plan = SubscriptionPlan(**data)
            db_session.add(plan)
        else:
            for key, value in data.items():
                setattr(plan, key, value)
        plans.append(plan)
    db_session.commit()
    return plans


def ensure_store_subscription(db_session, store_id: int, plan_code: str = "professional") -> StoreSubscription:
    seed_subscription_plans(db_session)
    subscription = (
        db_session.query(StoreSubscription)
        .filter_by(store_id=store_id)
        .order_by(StoreSubscription.created_at.desc())
        .first()
    )
    if subscription is not None:
        return subscription

    store = db_session.query(Store).filter_by(id=store_id).one()
    plan = db_session.query(SubscriptionPlan).filter_by(code=plan_code).one()
    subscription = StoreSubscription(
        store_id=store.id,
        plan_id=plan.id,
        status="trial",
        trial_ends_at=datetime.utcnow() + timedelta(days=7),
        current_period_ends_at=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription


def consume_ai_quota(db_session, store_id: int, units: int) -> bool:
    if units <= 0:
        return True
    subscription = ensure_store_subscription(db_session, store_id)
    refresh_subscription_status(subscription)
    if subscription.status == "trial_expired":
        db_session.commit()
        return False
    plan_quota = subscription.plan.ai_quota_monthly if subscription.plan else 0
    if subscription.ai_quota_used + units > plan_quota:
        return False
    # Atomic SQL update: only increment if still within quota
    result = (
        db_session.query(StoreSubscription)
        .filter(
            StoreSubscription.id == subscription.id,
            StoreSubscription.ai_quota_used + units <= plan_quota,
        )
        .update(
            {StoreSubscription.ai_quota_used: StoreSubscription.ai_quota_used + units},
            synchronize_session="fetch",
        )
    )
    db_session.commit()
    if result == 0:
        return False
    db_session.refresh(subscription)
    return True


def refresh_subscription_status(subscription: StoreSubscription, now: datetime | None = None) -> StoreSubscription:
    current = now or datetime.utcnow()
    if subscription.status == "trial" and subscription.trial_ends_at and subscription.trial_ends_at < current:
        subscription.status = "trial_expired"
    return subscription


def subscription_status_label(subscription: StoreSubscription) -> str:
    refresh_subscription_status(subscription)
    return {
        "trial": "试用中",
        "trial_expired": "试用已到期",
        "active": "付费中",
        "past_due": "待续费",
        "cancelled": "已取消",
    }.get(subscription.status, subscription.status)


def trial_days_left(subscription: StoreSubscription, now: datetime | None = None) -> int:
    if not subscription.trial_ends_at:
        return 0
    current = now or datetime.utcnow()
    if subscription.trial_ends_at < current:
        return 0
    return max((subscription.trial_ends_at.date() - current.date()).days, 0)
