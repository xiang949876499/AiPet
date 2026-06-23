from __future__ import annotations

from datetime import date, timedelta

from app.models import ContentItem
from content_engine.generator import list_templates


def build_content_calendar(session, store_id: int, start: date | None = None, days: int = 7) -> list[dict]:
    first_day = start or date.today()
    templates = list_templates()
    scheduled = {
        item.scheduled_date: item
        for item in session.query(ContentItem).filter_by(store_id=store_id).all()
        if item.scheduled_date is not None
    }
    result = []
    for offset in range(days):
        current = first_day + timedelta(days=offset)
        item = scheduled.get(current)
        template = templates[offset % len(templates)] if templates else {"code": "manual", "channel": "manual"}
        result.append(
            {
                "date": current.isoformat(),
                "template_code": item.topic if item else template.get("code"),
                "channel": item.channel if item else template.get("channel"),
                "status": item.status if item else "planned",
                "title": item.title if item else template.get("title", ""),
            }
        )
    return result
