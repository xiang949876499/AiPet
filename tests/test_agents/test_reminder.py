def test_reminder_agent_creates_due_washing_task(db_session, sample_records):
    from agents.reminder import ReminderAgent
    from app.models import FollowTask

    agent = ReminderAgent(db_session=db_session)
    result = agent.execute({"store_id": sample_records["store"].id})

    assert result["created"] == 1
    task = db_session.query(FollowTask).one()
    assert task.task_type == "洗护提醒"
    assert task.priority == "高"
    assert "24 天" in task.reason
    assert "豆豆" in task.ai_message


def test_reminder_agent_does_not_duplicate_open_task(db_session, sample_records):
    from agents.reminder import ReminderAgent

    agent = ReminderAgent(db_session=db_session)
    first = agent.execute({"store_id": sample_records["store"].id})
    second = agent.execute({"store_id": sample_records["store"].id})

    assert first["created"] == 1
    assert second["created"] == 0
