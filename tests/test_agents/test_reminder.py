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


def test_reminder_agent_uses_llm_to_optimize_message(db_session, sample_records):
    from agents.reminder import ReminderAgent
    from app.models import FollowTask
    from core.llm import LLMClient

    prompts = []
    llm = LLMClient(generator=lambda prompt: prompts.append(prompt) or "张姐，豆豆到洗护周期啦，这两天有空我帮您先留个清爽洗护时间。")

    result = ReminderAgent(db_session=db_session, llm=llm).execute({"store_id": sample_records["store"].id})

    task = db_session.query(FollowTask).one()
    assert result["created"] == 1
    assert task.ai_message == "张姐，豆豆到洗护周期啦，这两天有空我帮您先留个清爽洗护时间。"
    assert "客户称呼：张姐" in prompts[0]
    assert "宠物名称：豆豆" in prompts[0]


def test_reminder_agent_does_not_duplicate_open_task(db_session, sample_records):
    from agents.reminder import ReminderAgent

    agent = ReminderAgent(db_session=db_session)
    first = agent.execute({"store_id": sample_records["store"].id})
    second = agent.execute({"store_id": sample_records["store"].id})

    assert first["created"] == 1
    assert second["created"] == 0


def test_reminder_agent_skips_do_not_disturb_customer(db_session, sample_records):
    from agents.reminder import ReminderAgent
    from app.models import FollowTask

    sample_records["customer"].do_not_disturb = True
    db_session.commit()

    result = ReminderAgent(db_session=db_session).execute({"store_id": sample_records["store"].id})

    assert result["created"] == 0
    assert db_session.query(FollowTask).count() == 0
