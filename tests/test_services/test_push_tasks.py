def test_create_internal_push_task_from_follow_task(db_session, sample_records):
    from app.models import FollowTask, Staff
    from services.push_tasks import create_internal_push_task

    staff = Staff(store_id=sample_records["store"].id, name="小王", wecom_userid="wang")
    follow = FollowTask(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        task_type="洗护提醒",
        priority="高",
        reason="豆豆上次洗护距今 24 天",
        suggested_action="发送温和预约提醒",
        ai_message="张姐，豆豆该洗护了。",
    )
    db_session.add_all([staff, follow])
    db_session.commit()

    push_task = create_internal_push_task(db_session, follow.id, staff.id)

    assert push_task.channel == "wecom_internal"
    assert push_task.receiver_type == "staff"
    assert push_task.receiver_id == "wang"
    assert push_task.status == "pending"
    assert "张姐" in push_task.content
    assert "豆豆" in push_task.content
    assert "豆豆上次洗护距今 24 天" in push_task.content
