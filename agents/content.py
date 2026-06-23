from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ContentItem, Store
from core.llm import LLMClient
from services.credits import content_credit_cost
from services.subscriptions import consume_ai_quota


class ContentAgent:
    channels = ["朋友圈", "小红书", "短视频脚本"]

    def __init__(self, db_session: Session, llm: LLMClient | None = None):
        self.db_session = db_session
        self.llm = llm or LLMClient()

    def execute(self, context: dict) -> dict:
        store_id = context.get("store_id")
        store = self.db_session.query(Store).filter_by(id=store_id).first() if store_id else self.db_session.query(Store).first()
        if store is None:
            return {"created": 0}

        channels_to_create = [channel for channel in self.channels if not self._has_today_content(store.id, channel)]
        if channels_to_create and not consume_ai_quota(
            self.db_session, store.id, content_credit_cost(channels_to_create)
        ):
            return {"created": 0, "quota_blocked": True}

        created = 0
        base_time = datetime.utcnow()
        for index, channel in enumerate(channels_to_create):
            title, body = self._generate(channel, store.name)
            self.db_session.add(
                ContentItem(
                    store_id=store.id,
                    channel=channel,
                    topic="客户维系与洗护复购",
                    title=title,
                    body=body,
                    status="draft",
                    scheduled_at=base_time + timedelta(hours=index * 2),
                )
            )
            created += 1
        self.db_session.commit()
        return {"created": created}

    def _has_today_content(self, store_id: int, channel: str) -> bool:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        return (
            self.db_session.query(ContentItem)
            .filter(
                ContentItem.store_id == store_id,
                ContentItem.channel == channel,
                ContentItem.created_at >= today,
                ContentItem.created_at < tomorrow,
            )
            .count()
            > 0
        )

    def _generate(self, channel: str, store_name: str) -> tuple[str, str]:
        prompt = f"为{store_name}生成一条{channel}内容，主题是宠物洗护复购和客户维系，输出标题和正文。"
        generated = self.llm.generate(prompt)
        if generated:
            title, body = _parse_generated(generated)
            return title, body
        return "今日客户维系提醒", f"{store_name}今日建议发布一条洗护关怀内容，提醒毛孩子家长按周期预约清爽洗护。"


def _parse_generated(text: str) -> tuple[str, str]:
    title = "今日客户维系提醒"
    body = text.strip()
    for line in text.splitlines():
        if line.startswith("标题："):
            title = line.removeprefix("标题：").strip() or title
        if line.startswith("正文："):
            body = line.removeprefix("正文：").strip() or body
    return title, body
