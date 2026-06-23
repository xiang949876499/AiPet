from datetime import datetime, timedelta


def test_customer_segments_and_opportunities_prioritize_due_and_dormant_customers(db_session, sample_records):
    from app.models import Customer, Pet, ServiceRecord
    from services.ops_dashboard import build_customer_opportunities

    store = sample_records["store"]
    dormant = Customer(
        store_id=store.id,
        name="陈姐",
        phone="13700000000",
        last_visit_time=datetime.utcnow() - timedelta(days=96),
        visit_count=1,
    )
    db_session.add(dormant)
    db_session.flush()
    dormant_pet = Pet(store_id=store.id, customer_id=dormant.id, name="糯米", care_cycle_days=21)
    db_session.add(dormant_pet)
    db_session.flush()
    db_session.add(
        ServiceRecord(
            store_id=store.id,
            customer_id=dormant.id,
            pet_id=dormant_pet.id,
            service_type="洗护",
            service_time=datetime.utcnow() - timedelta(days=96),
            amount=128,
        )
    )
    db_session.commit()

    opportunities = build_customer_opportunities(db_session, store.id)

    assert opportunities[0]["customer_name"] == "陈姐"
    assert opportunities[0]["segment"] == "沉睡客户"
    assert opportunities[0]["suggested_action"] == "发送沉睡唤醒关怀"
    assert any(item["segment"] == "洗护到期" for item in opportunities)


def test_ops_metrics_count_touch_tasks_content_and_estimated_revenue(db_session, sample_records):
    from app.models import ContentItem, FollowTask
    from services.ops_dashboard import build_ops_metrics

    store = sample_records["store"]
    customer = sample_records["customer"]
    pet = sample_records["pet"]
    db_session.add_all(
        [
            FollowTask(
                store_id=store.id,
                customer_id=customer.id,
                pet_id=pet.id,
                task_type="洗护提醒",
                priority="高",
                reason="豆豆洗护到期",
                suggested_action="发送预约提醒",
                status="待处理",
                ai_message="张姐，豆豆该洗护啦。",
            ),
            ContentItem(
                store_id=store.id,
                channel="小红书",
                topic="洗护知识",
                title="柯基夏天洗护小贴士",
                body="短腿宝贝夏天更要注意脚底清洁。",
                status="draft",
            ),
        ]
    )
    db_session.commit()

    metrics = build_ops_metrics(db_session, store.id)

    assert metrics["weekly_touch_tasks"] == 1
    assert metrics["weekly_content_items"] == 1
    assert metrics["estimated_recovered_revenue"] == 128


def test_seed_subscription_plans_creates_recommended_professional_tier(db_session):
    from services.subscriptions import seed_subscription_plans
    from app.models import SubscriptionPlan

    seed_subscription_plans(db_session)

    plans = {plan.code: plan for plan in db_session.query(SubscriptionPlan).all()}
    assert set(plans) == {"experience", "starter", "professional", "growth"}
    assert plans["professional"].is_recommended is True
    assert plans["professional"].monthly_price == 499
    assert plans["professional"].ai_quota_monthly == 1500


def test_subscription_snapshot_includes_trial_status(db_session, sample_records):
    from services.ops_dashboard import build_subscription_snapshot
    from services.subscriptions import ensure_store_subscription

    ensure_store_subscription(db_session, sample_records["store"].id, "professional")

    snapshot = build_subscription_snapshot(db_session, sample_records["store"].id)

    assert snapshot["plan_name"] == "专业版"
    assert snapshot["status_label"] == "试用中"
    assert snapshot["trial_days_left"] == 7


def test_subscription_snapshot_marks_expired_trial(db_session, sample_records):
    from services.ops_dashboard import build_subscription_snapshot
    from services.subscriptions import ensure_store_subscription

    subscription = ensure_store_subscription(db_session, sample_records["store"].id, "professional")
    subscription.trial_ends_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    snapshot = build_subscription_snapshot(db_session, sample_records["store"].id)

    assert snapshot["trial_days_left"] == 0
    assert snapshot["status_label"] == "试用已到期"
