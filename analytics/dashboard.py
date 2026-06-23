from __future__ import annotations

from analytics.metrics import calculate_growth_metrics, calculate_professional_metrics, calculate_starter_metrics
from services.ops_dashboard import build_customer_opportunities, build_ops_metrics, build_subscription_snapshot


def build_tiered_dashboard(session, store_id: int, plan_code: str) -> dict:
    result = {
        "plan_code": plan_code,
        "tier": "starter",
        "subscription": build_subscription_snapshot(session, store_id),
        "ops_metrics": build_ops_metrics(session, store_id),
        "opportunities": build_customer_opportunities(session, store_id),
        "features_blocked": [],
    }

    if plan_code == "starter":
        metrics = calculate_starter_metrics(session, store_id)
        result["metrics"] = metrics
        result["action_recommendations"] = build_action_recommendations(metrics)
        result["features_blocked"] = ["conversion funnel", "customer health", "content calendar"]
        return result

    # calculate_professional_metrics already includes starter metrics — no double call
    professional = calculate_professional_metrics(session, store_id)
    result.update(
        {
            "tier": "professional",
            "metrics": professional,
            "conversion_funnel": professional["conversion_funnel"],
            "approach_comparison": professional["approach_comparison"],
            "customer_health": professional["customer_health"],
            "action_recommendations": build_action_recommendations(professional),
        }
    )
    if plan_code in {"growth", "managed"}:
        result["tier"] = "growth"
        result["growth"] = calculate_growth_metrics(session, store_id)
    return result


def build_action_recommendations(metrics: dict) -> list[dict]:
    recommendations = []
    if metrics.get("pending_outreach_tasks", 0) > 0:
        recommendations.append({"type": "outreach", "title": "Process pending outreach", "detail": "Review scripts and record outcomes."})
    if metrics.get("reply_rate", 0) < 20:
        recommendations.append({"type": "script", "title": "Try a warmer script", "detail": "Current reply rate is below target."})
    if metrics.get("estimated_recovered_revenue", 0) <= 0:
        recommendations.append({"type": "attribution", "title": "Backfill visit outcomes", "detail": "Record service within 7 days to show recovered revenue."})
    if not recommendations:
        recommendations.append({"type": "steady", "title": "Daily loop is healthy", "detail": "Keep confirming tasks and updating outcomes."})
    return recommendations
