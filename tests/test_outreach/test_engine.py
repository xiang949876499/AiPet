from datetime import datetime, timedelta


def test_dispatch_outreach_creates_follow_task_and_log(db_session, sample_records):
    from app.models import FollowTask, OutreachLog
    from outreach.engine import dispatch_outreach

    result = dispatch_outreach(db_session, sample_records["store"].id)

    assert result["created"] >= 1
    assert db_session.query(FollowTask).count() >= 1
    log = db_session.query(OutreachLog).one()
    assert log.decision_card is not None
    assert log.status in {"pending_confirm", "pending_send"}


def test_dnd_and_frequency_caps_block_dispatch(db_session, sample_records):
    from app.models import OutreachLog
    from outreach.engine import can_dispatch_to_customer

    customer = sample_records["customer"]
    customer.do_not_disturb = True
    db_session.commit()
    allowed = can_dispatch_to_customer(db_session, customer, "wecom_external", "service")
    assert allowed["allowed"] is False

    customer.do_not_disturb = False
    db_session.add(
        OutreachLog(
            store_id=customer.store_id,
            customer_id=customer.id,
            rule_code="grooming_due",
            status="sent",
            sent_at=datetime.utcnow() - timedelta(hours=1),
        )
    )
    db_session.commit()

    allowed = can_dispatch_to_customer(db_session, customer, "wecom_external", "service")
    assert allowed["allowed"] is False
    assert "daily" in allowed["reason"]
