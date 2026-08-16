from __future__ import annotations

from datetime import datetime

from app.models import Customer, OutreachLog
from outreach.content_auditor import audit_content
from outreach.engine import can_dispatch_to_customer


def send_auto_outreach(session, client, plan_code: str = "starter", limit: int = 50) -> dict:
    sent = 0
    failed = 0
    logs = (
        session.query(OutreachLog)
        .filter_by(status="pending_send", send_mode="auto")
        .order_by(OutreachLog.created_at.asc(), OutreachLog.id.asc())
        .limit(limit)
        .all()
    )
    for log in logs:
        customer = session.get(Customer, log.customer_id)
        if customer is None:
            _fail(log, "missing customer")
            failed += 1
            continue
        if customer.push_consent_status != "authorized" or not customer.external_userid:
            _fail(log, "missing external contact authorization")
            failed += 1
            continue
        audit = audit_content(log.content)
        if not audit["passed"]:
            _fail(log, "sensitive words: " + ",".join(audit["blocked_terms"]))
            failed += 1
            continue
        guard = can_dispatch_to_customer(session, customer, log.channel, log.message_type, plan_code)
        if not guard["allowed"]:
            _fail(log, guard["reason"])
            failed += 1
            continue
        if client is None:
            _fail(log, "missing wecom client")
            failed += 1
            continue
        result = client.send_external_text(customer.external_userid, log.content)
        if int(result.get("errcode") or 0) == 0:
            log.status = "sent"
            log.sent_at = datetime.utcnow()
            log.error_message = None
            sent += 1
        else:
            _fail(log, result.get("errmsg") or "wecom send failed")
            failed += 1
    session.commit()
    return {"sent": sent, "failed": failed}


def _fail(log: OutreachLog, reason: str) -> None:
    log.status = "failed"
    log.error_message = reason
