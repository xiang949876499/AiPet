from app.models import FollowTask, PushTask, Staff


def create_internal_push_task(db_session, follow_task_id: int, staff_id: int) -> PushTask:
    follow_task = db_session.get(FollowTask, follow_task_id)
    if follow_task is None:
        raise ValueError(f"follow task {follow_task_id} not found")

    staff = db_session.get(Staff, staff_id)
    if staff is None:
        raise ValueError(f"staff {staff_id} not found")
    if not staff.wecom_userid:
        raise ValueError("staff has no wecom_userid")

    content_parts = [
        f"客户：{follow_task.customer.name}",
        f"宠物：{follow_task.pet.name}",
        f"原因：{follow_task.reason}",
        f"建议：{follow_task.suggested_action}",
    ]
    if follow_task.ai_message:
        content_parts.append(f"话术：{follow_task.ai_message}")

    push_task = PushTask(
        store_id=follow_task.store_id,
        follow_task_id=follow_task.id,
        channel="wecom_internal",
        receiver_type="staff",
        receiver_id=staff.wecom_userid,
        scene="repurchase_reminder",
        content="\n".join(content_parts),
    )
    db_session.add(push_task)
    db_session.commit()
    db_session.refresh(push_task)
    return push_task
