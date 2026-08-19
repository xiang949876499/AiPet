def test_credit_plan_quotas_and_task_costs(db_session):
    from app.models import SubscriptionPlan
    from services.credits import CREDIT_COSTS, credit_cost
    from services.subscriptions import seed_subscription_plans

    seed_subscription_plans(db_session)

    plans = {plan.code: plan for plan in db_session.query(SubscriptionPlan).all()}
    assert plans["experience"].name == "体验版"
    assert plans["experience"].monthly_price == 19
    assert plans["experience"].ai_quota_monthly == 100
    assert plans["starter"].ai_quota_monthly == 500
    assert plans["professional"].ai_quota_monthly == 1500
    assert plans["growth"].ai_quota_monthly == 3000
    assert "managed" not in plans

    assert CREDIT_COSTS["outreach_script"] == 1
    assert CREDIT_COSTS["activity_plan"] == 5
    assert CREDIT_COSTS["activity_image"] == 3
    assert CREDIT_COSTS["store_audit"] == 20
    assert CREDIT_COSTS["weekly_report"] == 20
    assert credit_cost("douyin_script") == 3


def test_consume_credit_task_updates_subscription_snapshot(db_session, sample_records):
    from services.credits import consume_credit_task
    from services.ops_dashboard import build_subscription_snapshot
    from services.subscriptions import ensure_store_subscription

    subscription = ensure_store_subscription(db_session, sample_records["store"].id, "starter")

    assert consume_credit_task(db_session, sample_records["store"].id, "activity_plan") is True
    assert subscription.ai_quota_used == 5

    snapshot = build_subscription_snapshot(db_session, sample_records["store"].id)

    assert snapshot["credit_used"] == 5
    assert snapshot["credit_total"] == 500
    assert snapshot["credit_remaining"] == 495
    assert snapshot["credit_usage_label"] == "本月已用 5 / 500 Credit"


def test_consume_credit_task_blocks_when_credit_is_exhausted(db_session, sample_records):
    from services.credits import consume_credit_task
    from services.subscriptions import ensure_store_subscription

    subscription = ensure_store_subscription(db_session, sample_records["store"].id, "experience")
    subscription.ai_quota_used = 95
    db_session.commit()

    assert consume_credit_task(db_session, sample_records["store"].id, "activity_plan") is True
    assert subscription.ai_quota_used == 100

    subscription.ai_quota_used = subscription.plan.ai_quota_monthly
    db_session.commit()

    assert consume_credit_task(db_session, sample_records["store"].id, "weekly_report") is False
