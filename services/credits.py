from services.subscriptions import consume_ai_quota


CREDIT_COSTS = {
    "outreach_script": 1,
    "review_reply": 1,
    "moments_copy": 2,
    "xiaohongshu_copy": 2,
    "douyin_script": 3,
    "activity_plan": 5,
    "dormant_recall_batch": 5,
    "seven_day_plan": 10,
    "store_audit": 20,
    "weekly_report": 20,
    "advisor_question": 1,
}


CONTENT_CHANNEL_TASKS = {
    "朋友圈": "moments_copy",
    "小红书": "xiaohongshu_copy",
    "短视频脚本": "douyin_script",
}


def credit_cost(task_type: str) -> int:
    return CREDIT_COSTS.get(task_type, 1)


def content_credit_cost(channels: list[str]) -> int:
    return sum(credit_cost(CONTENT_CHANNEL_TASKS.get(channel, "moments_copy")) for channel in channels)


def consume_credit_task(db_session, store_id: int, task_type: str, quantity: int = 1) -> bool:
    return consume_ai_quota(db_session, store_id, credit_cost(task_type) * max(quantity, 1))
