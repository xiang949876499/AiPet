from datetime import datetime


def _make_washing_task(db_session, sample_records):
    from app.models import FollowTask

    task = FollowTask(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        task_type="洗护提醒",
        priority="高",
        reason="豆豆上次洗护距今 24 天，最近 7 天没有预约",
        suggested_action="发送温和预约提醒",
        due_date=datetime.utcnow(),
        status="待处理",
        ai_message="张姐，豆豆上次洗护已经有一阵子啦。这周如果方便，我可以先帮您留一个顺手的时间，您看哪天合适？",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def test_friendly_message_prompt_asks_for_value_based_copy(db_session, sample_records):
    from web.routes.reminders import _friendly_message_prompt

    task = _make_washing_task(db_session, sample_records)

    prompt = _friendly_message_prompt(task)

    assert "先给客户一个明确的预约理由" in prompt
    assert "过程 + 效果 + 风险降低" in prompt
    assert "不要只重复“有一阵子”" in prompt
    assert "只输出一条可直接复制发送给客户的微信话术" in prompt
    assert "客户：张姐" in prompt
    assert "宠物：豆豆" in prompt


def test_fallback_friendly_message_is_specific_enough_to_notice_change(db_session, sample_records):
    from web.routes.reminders import _fallback_friendly_message

    task = _make_washing_task(db_session, sample_records)

    message = _fallback_friendly_message(task)

    assert "豆豆上次洗护距今 24 天" in message
    assert "基础洗护" in message
    assert "吹干" in message
    assert "顺便看一下毛发和脚底状态" in message
    assert "您看今天或明天哪个时间方便" in message
    assert "一阵子啦" not in message


def test_skip_reminder_marks_task_skipped(db_session, sample_records):
    from web.routes.reminders import skip_reminder

    task = _make_washing_task(db_session, sample_records)

    payload = skip_reminder(task.id, db_session)

    assert payload["status"] == "已跳过"
    assert payload["result"] == "已跳过"


def test_update_reminder_message_persists_copy(db_session, sample_records):
    from web.routes.reminders import update_reminder_message

    task = _make_washing_task(db_session, sample_records)

    payload = update_reminder_message(task.id, {"message": "张姐，豆豆这周可以安排护理吗？"}, db_session)

    assert payload["ai_message"] == "张姐，豆豆这周可以安排护理吗？"
