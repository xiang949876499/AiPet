from datetime import datetime, timedelta


def test_starter_metrics_include_ai_value_and_attribution(db_session, sample_records):
    from app.models import FollowTask, OutreachLog, ServiceRecord
    from analytics.metrics import calculate_starter_metrics

    store_id = sample_records["store"].id
    customer_id = sample_records["customer"].id
    pet_id = sample_records["pet"].id
    db_session.add(
        FollowTask(
            store_id=store_id,
            customer_id=customer_id,
            pet_id=pet_id,
            task_type="grooming_due",
            reason="due",
            suggested_action="send",
        )
    )
    db_session.add(
        OutreachLog(
            store_id=store_id,
            customer_id=customer_id,
            pet_id=pet_id,
            status="sent",
            sent_at=datetime.utcnow() - timedelta(days=1),
            response_time=datetime.utcnow(),
            attributed_revenue=128,
            service_within_7d=True,
        )
    )
    db_session.add(
        ServiceRecord(
            store_id=store_id,
            customer_id=customer_id,
            pet_id=pet_id,
            service_type="grooming",
            service_time=datetime.utcnow(),
            amount=128,
        )
    )
    db_session.commit()

    metrics = calculate_starter_metrics(db_session, store_id)

    assert metrics["ai_recommended_followups"] >= 1
    assert metrics["pending_outreach_tasks"] >= 1
    assert metrics["reply_rate"] == 100.0
    assert metrics["visit_conversion_7d"] == 100.0
    assert metrics["attributed_revenue"] == 128.0


def test_professional_metrics_add_customer_health(db_session, sample_records):
    from analytics.metrics import calculate_professional_metrics

    metrics = calculate_professional_metrics(db_session, sample_records["store"].id)

    assert "customer_health" in metrics
    assert metrics["customer_health"]["active"] >= 1
