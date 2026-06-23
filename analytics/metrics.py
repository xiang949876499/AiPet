from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from app.models import Customer, FollowTask, OutreachLog, ServiceRecord


PENDING_STATUSES = {"pending", "pending_confirm", "pending_send", "待处理"}


def calculate_starter_metrics(session, store_id: int, now: datetime | None = None) -> dict:
    current = now or datetime.utcnow()
    today_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = current - timedelta(days=7)

    ai_recommended = session.query(FollowTask).filter(FollowTask.store_id == store_id, FollowTask.created_at >= today_start).count()
    pending = (
        session.query(FollowTask)
        .filter(FollowTask.store_id == store_id, FollowTask.status.in_(list(PENDING_STATUSES)))
        .count()
    )
    sent = session.query(OutreachLog).filter(OutreachLog.store_id == store_id, OutreachLog.status == "sent").count()
    replied = (
        session.query(OutreachLog)
        .filter(
            OutreachLog.store_id == store_id,
            OutreachLog.status == "sent",
            (OutreachLog.response_time.is_not(None)) | (OutreachLog.response_content.is_not(None)),
        )
        .count()
    )
    yesterday_sent = (
        session.query(OutreachLog)
        .filter(OutreachLog.store_id == store_id, OutreachLog.sent_at >= yesterday_start, OutreachLog.sent_at < today_start)
        .count()
    )
    yesterday_converted = (
        session.query(OutreachLog)
        .filter(
            OutreachLog.store_id == store_id,
            OutreachLog.sent_at >= yesterday_start,
            OutreachLog.sent_at < today_start,
            OutreachLog.service_within_7d == True,
        )
        .count()
    )
    attributed_revenue = (
        session.query(func.coalesce(func.sum(OutreachLog.attributed_revenue), 0))
        .filter(OutreachLog.store_id == store_id)
        .scalar()
    )
    monthly_visits = (
        session.query(ServiceRecord)
        .filter(ServiceRecord.store_id == store_id, ServiceRecord.service_time >= month_start)
        .count()
    )
    weekly_revenue = (
        session.query(func.coalesce(func.sum(ServiceRecord.amount), 0))
        .filter(ServiceRecord.store_id == store_id, ServiceRecord.service_time >= week_start)
        .scalar()
    )
    customers = session.query(Customer).filter_by(store_id=store_id).count()
    return {
        "ai_recommended_followups": ai_recommended,
        "today_outreach": ai_recommended,
        "pending_outreach_tasks": pending,
        "pending_tasks": pending,
        "yesterday_outreach_to_visit": _rate(yesterday_converted, yesterday_sent),
        "estimated_recovered_revenue": float(attributed_revenue or 0),
        "reply_rate": _rate(replied, sent),
        "visit_conversion_7d": _rate(
            session.query(OutreachLog)
            .filter(OutreachLog.store_id == store_id, OutreachLog.status == "sent", OutreachLog.service_within_7d == True)
            .count(),
            sent,
        ),
        "attributed_revenue": float(attributed_revenue or 0),
        "monthly_visits": monthly_visits,
        "weekly_revenue": float(weekly_revenue or 0),
        "customers": customers,
    }


def calculate_professional_metrics(session, store_id: int, now: datetime | None = None) -> dict:
    current = now or datetime.utcnow()
    starter = calculate_starter_metrics(session, store_id, current)
    active = (
        session.query(Customer)
        .filter(Customer.store_id == store_id, Customer.last_visit_time >= current - timedelta(days=90))
        .count()
    )
    dormant = (
        session.query(Customer)
        .filter(
            Customer.store_id == store_id,
            Customer.last_visit_time < current - timedelta(days=90),
            Customer.last_visit_time >= current - timedelta(days=180),
        )
        .count()
    )
    lost = (
        session.query(Customer)
        .filter(Customer.store_id == store_id, Customer.last_visit_time < current - timedelta(days=180))
        .count()
    )
    return {
        **starter,
        "conversion_funnel": {
            "sent": _sent_count(session, store_id),
            "replied": _replied_count(session, store_id),
            "visited": _visited_count(session, store_id),
            "reply_rate": starter["reply_rate"],
            "visit_rate": starter["visit_conversion_7d"],
        },
        "approach_comparison": _approach_comparison(session, store_id),
        "customer_health": {"active": active, "dormant": dormant, "lost": lost},
    }


def calculate_growth_metrics(session, store_id: int) -> dict:
    customers = session.query(Customer).filter_by(store_id=store_id).all()
    total_spent = sum(float(customer.total_amount or 0) for customer in customers)
    avg_ltv = round(total_spent / len(customers), 2) if customers else 0
    churn_risk = [customer.name for customer in customers if customer.last_visit_time and customer.last_visit_time < datetime.utcnow() - timedelta(days=60)]
    return {"average_ltv": avg_ltv, "churn_risk_customers": churn_risk[:10], "outreach_roi": 0}


def _sent_count(session, store_id: int) -> int:
    return session.query(OutreachLog).filter_by(store_id=store_id, status="sent").count()


def _replied_count(session, store_id: int) -> int:
    return (
        session.query(OutreachLog)
        .filter(
            OutreachLog.store_id == store_id,
            OutreachLog.status == "sent",
            (OutreachLog.response_time.is_not(None)) | (OutreachLog.response_content.is_not(None)),
        )
        .count()
    )


def _visited_count(session, store_id: int) -> int:
    return session.query(OutreachLog).filter_by(store_id=store_id, status="sent", service_within_7d=True).count()


def _approach_comparison(session, store_id: int) -> dict:
    rows = (
        session.query(OutreachLog.rule_code, func.count(OutreachLog.id))
        .filter(OutreachLog.store_id == store_id)
        .group_by(OutreachLog.rule_code)
        .all()
    )
    return {rule_code or "unknown": count for rule_code, count in rows}


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 1) if total else 0.0
