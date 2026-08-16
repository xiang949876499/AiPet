from __future__ import annotations

from app.models import Customer, OutreachLog, Pet


def get_pending_confirmations(session, store_id: int) -> list[dict]:
    logs = (
        session.query(OutreachLog)
        .filter_by(store_id=store_id, status="pending_confirm")
        .order_by(OutreachLog.created_at.asc(), OutreachLog.id.asc())
        .all()
    )
    result = []
    for log in logs:
        customer = session.get(Customer, log.customer_id)
        pet = session.get(Pet, log.pet_id) if log.pet_id else None
        result.append(
            {
                "log_id": log.id,
                "customer_name": customer.name if customer else "",
                "pet_name": pet.name if pet else "",
                "rule_code": log.rule_code,
                "ai_message": log.content,
                "decision_card": log.decision_card,
            }
        )
    return result


def confirm_message(session, log_id: int, edited_content: str | None = None):
    log = session.get(OutreachLog, log_id)
    if log is None:
        raise ValueError(f"OutreachLog {log_id} not found")
    if edited_content is not None:
        log.content = edited_content
    log.status = "pending_send"
    session.commit()
    return log


def reject_message(session, log_id: int, reason: str = ""):
    log = session.get(OutreachLog, log_id)
    if log is None:
        raise ValueError(f"OutreachLog {log_id} not found")
    log.status = "cancelled"
    log.error_message = reason
    session.commit()
    return log
