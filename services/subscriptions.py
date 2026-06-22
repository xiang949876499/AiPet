from datetime import datetime, timedelta

from app.models import Store, StoreSubscription, SubscriptionPlan


DEFAULT_PLANS = [
    {
        "code": "starter",
        "name": "入门版",
        "monthly_price": 199,
        "annual_price": 1990,
        "ai_quota_monthly": 80,
        "features": "客户提醒,基础话术,手动复制发送",
        "is_recommended": False,
    },
    {
        "code": "professional",
        "name": "专业版",
        "monthly_price": 499,
        "annual_price": 4990,
        "ai_quota_monthly": 300,
        "features": "企业微信,内容日历,客户分层,复购追踪",
        "is_recommended": True,
    },
    {
        "code": "growth",
        "name": "增长版",
        "monthly_price": 999,
        "annual_price": 9990,
        "ai_quota_monthly": 900,
        "features": "活动Agent,自媒体批量生成,月度报告",
        "is_recommended": False,
    },
    {
        "code": "managed",
        "name": "代运营包",
        "monthly_price": 1999,
        "annual_price": 0,
        "ai_quota_monthly": 1500,
        "features": "内容规划,活动策划,素材托管",
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
