def test_auto_sender_requires_consent_and_external_userid(db_session, sample_records):
    from app.models import OutreachLog
    from outreach.auto_sender import send_auto_outreach

    customer = sample_records["customer"]
    customer.push_consent_status = "unknown"
    db_session.add(
        OutreachLog(
            store_id=customer.store_id,
            customer_id=customer.id,
            rule_code="grooming_due",
            status="pending_send",
            send_mode="auto",
            content="Safe reminder",
        )
    )
    db_session.commit()

    result = send_auto_outreach(db_session, client=None)

    assert result["sent"] == 0
    assert result["failed"] == 1


def test_auto_sender_sends_after_checks(db_session, sample_records):
    from app.models import OutreachLog
    from outreach.auto_sender import send_auto_outreach

    class Client:
        def send_external_text(self, external_userid: str, content: str):
            return {"errcode": 0, "errmsg": "ok"}

    customer = sample_records["customer"]
    customer.push_consent_status = "authorized"
    customer.external_userid = "external-1"
    db_session.add(
        OutreachLog(
            store_id=customer.store_id,
            customer_id=customer.id,
            rule_code="grooming_due",
            status="pending_send",
            send_mode="auto",
            content="Safe reminder",
        )
    )
    db_session.commit()

    result = send_auto_outreach(db_session, client=Client())

    assert result["sent"] == 1
    assert result["failed"] == 0
