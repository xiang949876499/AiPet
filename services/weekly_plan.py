from datetime import date, timedelta

from services.ops_dashboard import build_customer_opportunities


CHANNELS = ["朋友圈", "小红书", "短视频脚本"]
TOPICS = [
    "洗护到期客户关怀",
    "沉睡客户唤醒",
    "高频老客会员日",
    "夏季护理知识",
    "门店服务案例",
    "老带新活动预热",
    "本周预约收口",
]


def build_7_day_ops_plan(db_session, store_id: int, start_date: date | None = None) -> list[dict]:
    start = start_date or date.today()
    opportunities = build_customer_opportunities(db_session, store_id, limit=7)
    plan = []
    for index in range(7):
        opportunity = opportunities[index % len(opportunities)] if opportunities else None
        channel = CHANNELS[index % len(CHANNELS)]
        topic = TOPICS[index]
        plan.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "channel": channel,
                "content_topic": topic,
                "customer_focus": _customer_focus(opportunity),
                "suggested_action": _suggested_action(opportunity, channel),
                "talking_point": _talking_point(opportunity, topic),
            }
        )
    return plan


def _customer_focus(opportunity: dict | None) -> str:
    if not opportunity:
        return "全店客户 / 本周可预约家长"
    return f"{opportunity['customer_name']} / {opportunity['pet_name']}（{opportunity['segment']}）"


def _suggested_action(opportunity: dict | None, channel: str) -> str:
    if opportunity:
        return f"{opportunity['suggested_action']}，并同步准备{channel}内容"
    return f"发布{channel}内容，收集本周可预约客户"


def _talking_point(opportunity: dict | None, topic: str) -> str:
    if opportunity:
        return f"{opportunity['reason']}；话术重点：{opportunity['message']}"
    return f"{topic}：提醒家长按周期预约洗护，老板确认后再触达。"
