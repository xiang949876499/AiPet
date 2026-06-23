from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta

from app.models import Customer, FollowTask, OutreachLog
from outreach.rules import scan_all_rules


PLAN_DAILY_CAPS = {"starter": 50, "professional": 200, "growth": 500, "managed": 500}


def dispatch_outreach(session, store_id: int, plan_code: str = "starter", now: datetime | None = None) -> dict:
    current = now or datetime.utcnow()
    created = 0
    skipped = 0
    for hit in scan_all_rules(session, store_id, current):
        customer = session.get(Customer, hit["customer_id"])
        if customer is None:
            skipped += 1
            continue
        guard = can_dispatch_to_customer(session, customer, "wecom_external", hit.get("message_type", "service"), plan_code, current)
        if not guard["allowed"]:
            skipped += 1
            continue
        if _already_has_open_task(session, store_id, hit["customer_id"], hit["rule_code"]):
            skipped += 1
            continue
        decision_card = json.dumps(hit["decision_card"], ensure_ascii=False)
        task = FollowTask(
            store_id=store_id,
            customer_id=hit["customer_id"],
            pet_id=hit["pet_id"],
            task_type=hit["rule_code"],
            priority="high" if hit["rule_code"] in {"grooming_due", "dormant_wake"} else "medium",
            reason=hit["reason"],
            suggested_action=hit["suggested_action"],
            ai_message=hit["ai_message"],
            decision_card=decision_card,
            send_mode=hit.get("send_mode", "manual_confirm"),
            due_date=current,
        )
        session.add(task)
        session.flush()
        log = OutreachLog(
            store_id=store_id,
            customer_id=hit["customer_id"],
            pet_id=hit["pet_id"],
            follow_task_id=task.id,
            rule_code=hit["rule_code"],
            message_type=hit.get("message_type", "service"),
            send_mode=hit.get("send_mode", "manual_confirm"),
            content=hit["ai_message"],
            status="pending_confirm" if hit.get("send_mode") == "manual_confirm" else "pending_send",
            decision_card=decision_card,
        )
        session.add(log)
        created += 1
    session.commit()
    return {"created": created, "skipped": skipped}


def can_dispatch_to_customer(
    session,
    customer: Customer,
    channel: str,
    message_type: str,
    plan_code: str = "starter",
    now: datetime | None = None,
) -> dict:
    current = now or datetime.utcnow()
    if not _inside_store_hours(current):
        return {"allowed": False, "reason": "store quiet hours"}
    if customer.do_not_disturb:
        return {"allowed": False, "reason": "global dnd"}
    if customer.dnd_until and customer.dnd_until >= current:
        return {"allowed": False, "reason": "temporary dnd"}
    if _csv_contains(customer.dnd_channels, channel):
        return {"allowed": False, "reason": "channel dnd"}
    if _csv_contains(customer.dnd_message_types, message_type):
        return {"allowed": False, "reason": "message type dnd"}
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    daily_count = (
        session.query(OutreachLog)
        .filter(OutreachLog.customer_id == customer.id, OutreachLog.sent_at >= day_start, OutreachLog.status == "sent")
        .count()
    )
    if daily_count >= 1:
        return {"allowed": False, "reason": "daily frequency cap"}
    monthly_count = (
        session.query(OutreachLog)
        .filter(OutreachLog.customer_id == customer.id, OutreachLog.sent_at >= month_start, OutreachLog.status == "sent")
        .count()
    )
    if monthly_count >= 5:
        return {"allowed": False, "reason": "monthly frequency cap"}
    store_daily = (
        session.query(OutreachLog)
        .filter(OutreachLog.store_id == customer.store_id, OutreachLog.sent_at >= day_start, OutreachLog.status == "sent")
        .count()
    )
    if store_daily >= PLAN_DAILY_CAPS.get(plan_code, PLAN_DAILY_CAPS["starter"]):
        return {"allowed": False, "reason": "plan daily cap"}
    return {"allowed": True, "reason": "ok"}


def _already_has_open_task(session, store_id: int, customer_id: int, task_type: str) -> bool:
    since = datetime.utcnow() - timedelta(days=1)
    return (
        session.query(FollowTask)
        .filter(
            FollowTask.store_id == store_id,
            FollowTask.customer_id == customer_id,
            FollowTask.task_type == task_type,
            FollowTask.created_at >= since,
            FollowTask.status.in_(["pending", "待处理"]),
        )
        .count()
        > 0
    )


def _inside_store_hours(current: datetime) -> bool:
    local_offset_hours = int(os.getenv("AIPET_LOCAL_UTC_OFFSET_HOURS", "8"))
    local = (current + timedelta(hours=local_offset_hours)).time()
    return time(8, 0) <= local <= time(21, 0)


def _csv_contains(raw: str | None, value: str) -> bool:
    if not raw:
        return False
    return value in {part.strip() for part in raw.split(",") if part.strip()}
