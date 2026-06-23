from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Callable

from app.models import Customer, OutreachRule, Pet, ProductPurchase, SampleTrial, ServiceRecord


DEFAULT_RULES = [
    {"code": "grooming_due", "name": "Grooming due", "message_type": "service", "send_mode": "auto"},
    {"code": "dormant_wake", "name": "Dormant wake-up", "message_type": "service", "send_mode": "auto"},
    {"code": "trial_followup", "name": "Trial follow-up", "message_type": "service", "send_mode": "auto"},
    {"code": "vaccine_due", "name": "Vaccine due", "message_type": "care", "send_mode": "auto"},
    {"code": "deworming_due", "name": "Deworming due", "message_type": "care", "send_mode": "auto"},
    {"code": "pet_birthday", "name": "Pet birthday", "message_type": "marketing", "send_mode": "auto"},
    {"code": "festival_marketing", "name": "Festival marketing", "message_type": "marketing", "send_mode": "manual_confirm"},
    {"code": "product_repurchase", "name": "Product repurchase", "message_type": "repurchase", "send_mode": "auto"},
    {"code": "post_service_followup", "name": "Post-service follow-up", "message_type": "service", "send_mode": "auto"},
    {"code": "member_upgrade", "name": "Member upgrade", "message_type": "marketing", "send_mode": "manual_confirm"},
]


def _ensure_default_rules(session, store_id: int) -> list[OutreachRule]:
    existing = {rule.code: rule for rule in session.query(OutreachRule).filter_by(store_id=store_id).all()}
    created = []
    for item in DEFAULT_RULES:
        if item["code"] in existing:
            continue
        rule = OutreachRule(store_id=store_id, **item)
        session.add(rule)
        created.append(rule)
    if created:
        session.commit()
    return session.query(OutreachRule).filter_by(store_id=store_id).order_by(OutreachRule.id).all()


def enabled_rules(session, store_id: int) -> dict[str, OutreachRule]:
    _ensure_default_rules(session, store_id)
    return {rule.code: rule for rule in session.query(OutreachRule).filter_by(store_id=store_id, enabled=True).all()}


def scan_all_rules(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    scanners: list[Callable] = [
        scan_grooming_due,
        scan_dormant_customers,
        scan_trial_followup,
        scan_vaccine_due,
        scan_deworming_due,
        scan_pet_birthday,
        scan_festival_marketing,
        scan_product_repurchase,
        scan_post_service_followup,
        scan_member_upgrade,
    ]
    active = enabled_rules(session, store_id)
    hits = []
    for scanner in scanners:
        for hit in scanner(session, store_id, current):
            rule = active.get(hit["rule_code"])
            if not rule:
                continue
            hit["send_mode"] = rule.send_mode
            hit["message_type"] = rule.message_type
            hits.append(hit)
    return hits


def scan_grooming_due(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    rows = (
        session.query(ServiceRecord, Customer, Pet)
        .join(Customer, ServiceRecord.customer_id == Customer.id)
        .join(Pet, ServiceRecord.pet_id == Pet.id)
        .filter(ServiceRecord.store_id == store_id, ServiceRecord.service_type.like("%洗%"))
        .order_by(ServiceRecord.service_time.desc())
        .all()
    )
    latest_by_pet = {}
    for record, customer, pet in rows:
        latest_by_pet.setdefault(pet.id, (record, customer, pet))
    hits = []
    for record, customer, pet in latest_by_pet.values():
        days_since = (current - record.service_time).days
        if days_since >= pet.care_cycle_days:
            hits.append(_hit("grooming_due", customer, pet, {"last_grooming_date": _iso(record.service_time), "days_since": days_since, "suggested_cycle": pet.care_cycle_days}, "Book grooming follow-up."))
    return hits


def scan_dormant_customers(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    hits = []
    customers = session.query(Customer).filter_by(store_id=store_id).all()
    for customer in customers:
        if not customer.last_visit_time:
            continue
        days_since = (current - customer.last_visit_time).days
        if days_since >= 90:
            pet = customer.pets[0] if customer.pets else None
            hits.append(_hit("dormant_wake", customer, pet, {"last_visit_time": _iso(customer.last_visit_time), "days_since": days_since}, "Send gentle wake-up message."))
    return hits


def scan_trial_followup(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    hits = []
    trials = session.query(SampleTrial).filter_by(store_id=store_id).all()
    customers = {item.id: item for item in session.query(Customer).filter_by(store_id=store_id).all()}
    pets = {item.id: item for item in session.query(Pet).filter_by(store_id=store_id).all()}
    for trial in trials:
        if trial.follow_time is None and (current - trial.receive_time).days >= 1:
            hits.append(_hit("trial_followup", customers[trial.customer_id], pets.get(trial.pet_id), {"receive_time": _iso(trial.receive_time)}, "Ask for sample feedback."))
    return hits


def scan_vaccine_due(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = (now or datetime.utcnow()).date()
    return [
        _hit("vaccine_due", pet.customer, pet, {"vaccine_next_date": pet.vaccine_next_date.isoformat()}, "Remind vaccine due date.")
        for pet in session.query(Pet).filter_by(store_id=store_id).all()
        if pet.vaccine_next_date and current <= pet.vaccine_next_date <= current + timedelta(days=7)
    ]


def scan_deworming_due(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = (now or datetime.utcnow()).date()
    hits = []
    for pet in session.query(Pet).filter_by(store_id=store_id).all():
        if pet.deworming_last_date and (current - pet.deworming_last_date).days >= 30:
            hits.append(_hit("deworming_due", pet.customer, pet, {"deworming_last_date": pet.deworming_last_date.isoformat()}, "Remind deworming."))
    return hits


def scan_pet_birthday(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = (now or datetime.utcnow()).date()
    return [
        _hit("pet_birthday", pet.customer, pet, {"birthday": pet.birthday.isoformat()}, "Send birthday greeting.")
        for pet in session.query(Pet).filter_by(store_id=store_id).all()
        if pet.birthday and _same_month_day(pet.birthday, current)
    ]


def scan_festival_marketing(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    if current.day not in {1, 15}:
        return []
    return [_hit("festival_marketing", customer, customer.pets[0] if customer.pets else None, {"date": current.date().isoformat()}, "Prepare festival message.") for customer in session.query(Customer).filter_by(store_id=store_id).limit(20)]


def scan_product_repurchase(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    hits = []
    for purchase in session.query(ProductPurchase).filter_by(store_id=store_id).all():
        if purchase.next_remind_time and purchase.next_remind_time <= current:
            customer = session.get(Customer, purchase.customer_id)
            pet = session.get(Pet, purchase.pet_id)
            if customer:
                hits.append(_hit("product_repurchase", customer, pet, {"next_remind_time": _iso(purchase.next_remind_time)}, "Remind product repurchase."))
    return hits


def scan_post_service_followup(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    since = current - timedelta(days=2)
    hits = []
    for record in session.query(ServiceRecord).filter(ServiceRecord.store_id == store_id, ServiceRecord.service_time >= since).all():
        hits.append(_hit("post_service_followup", record.customer, record.pet, {"service_time": _iso(record.service_time)}, "Ask about service satisfaction."))
    return hits


def scan_member_upgrade(session, store_id: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.utcnow()
    # Only scan customers whose last visit was within 90 days to avoid re-triggering on every scan
    since = current - timedelta(days=90)
    hits = []
    for customer in (
        session.query(Customer)
        .filter(
            Customer.store_id == store_id,
            Customer.total_amount >= 1000,
            Customer.last_visit_time >= since,
        )
        .all()
    ):
        pet = customer.pets[0] if customer.pets else None
        hits.append(_hit("member_upgrade", customer, pet, {"total_spent": float(customer.total_amount or 0), "visit_count": customer.visit_count}, "Invite member upgrade."))
    return hits


def _hit(rule_code: str, customer: Customer, pet: Pet | None, evidence: dict, suggestion: str) -> dict:
    context = {
        "name": customer.name,
        "tier": "VIP" if float(customer.total_amount or 0) >= 1000 or customer.visit_count >= 8 else "regular",
        "total_spent": float(customer.total_amount or 0),
        "visit_count": customer.visit_count,
    }
    decision_card = {
        "trigger_rule": rule_code,
        "evidence": evidence,
        "customer_context": context,
        "suggestion": suggestion,
    }
    return {
        "rule_code": rule_code,
        "customer_id": customer.id,
        "pet_id": pet.id if pet else None,
        "reason": json.dumps(evidence, ensure_ascii=False),
        "suggested_action": suggestion,
        "ai_message": _script_for(customer, pet, rule_code),
        "decision_card": decision_card,
    }


def _script_for(customer: Customer, pet: Pet | None, rule_code: str) -> str:
    pet_name = pet.name if pet else "your pet"
    return f"Hi {customer.name}, {pet_name} has a new {rule_code.replace('_', ' ')} reminder from the store."


def _iso(value: datetime | date) -> str:
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def _same_month_day(value: datetime | date, current: date) -> bool:
    day = value.date() if isinstance(value, datetime) else value
    return day.month == current.month and day.day == current.day
