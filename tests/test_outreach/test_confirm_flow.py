def test_confirm_flow_lists_and_confirms_messages(db_session, sample_records):
    from app.models import OutreachLog
    from outreach.confirm_flow import confirm_message, get_pending_confirmations

    log = OutreachLog(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        rule_code="member_upgrade",
        status="pending_confirm",
        content="VIP script",
        decision_card='{"trigger_rule": "member_upgrade"}',
    )
    db_session.add(log)
    db_session.commit()

    pending = get_pending_confirmations(db_session, sample_records["store"].id)
    assert pending[0]["customer_name"] == sample_records["customer"].name

    updated = confirm_message(db_session, log.id)
    assert updated.status == "pending_send"
