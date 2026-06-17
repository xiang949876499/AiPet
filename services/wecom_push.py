from datetime import datetime

from app.models import PushTask


def send_push_task(db_session, push_task_id: int, wecom_client) -> dict:
    push_task = db_session.get(PushTask, push_task_id)
    if push_task is None:
        raise ValueError(f"push task {push_task_id} not found")

    if push_task.status not in {"pending", "approved"}:
        return {"sent": False, "skipped": True, "reason": f"status:{push_task.status}"}

    if push_task.channel != "wecom_internal":
        return {"sent": False, "skipped": True, "reason": f"channel:{push_task.channel}"}

    result = wecom_client.send_internal_text(push_task.receiver_id, push_task.content)
    if result.get("errcode") == 0:
        push_task.status = "sent"
        push_task.sent_at = datetime.utcnow()
        push_task.error_message = None
        db_session.commit()
        return {"sent": True, "result": result}

    push_task.status = "failed"
    push_task.error_message = result.get("errmsg") or str(result)
    db_session.commit()
    return {"sent": False, "result": result}
