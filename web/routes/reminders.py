from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import FollowTask
from web.routes.deps import get_db

router = APIRouter()

STATUS_ALIASES = {
    "pending": "待处理",
    "sent": "已发送",
    "replied": "已回复",
    "booked": "已预约",
    "rejected": "已拒绝",
    "skipped": "已跳过",
}


def _normalize_status(status: str | None) -> str | None:
    if not status:
        return None
    return STATUS_ALIASES.get(status, status)


def _task_payload(task: FollowTask) -> dict:
    return {
        "id": task.id,
        "customer_id": task.customer_id,
        "customer_name": task.customer.name,
        "pet_id": task.pet_id,
        "pet_name": task.pet.name,
        "task_type": task.task_type,
        "priority": task.priority,
        "reason": task.reason,
        "suggested_action": task.suggested_action,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "status": task.status,
        "ai_message": task.ai_message,
        "result": task.result,
    }


@router.get("")
def list_reminders(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = db.query(FollowTask).order_by(FollowTask.created_at.desc(), FollowTask.id.desc())
    normalized_status = _normalize_status(status)
    if normalized_status:
        query = query.filter(FollowTask.status == normalized_status)
    return [_task_payload(task) for task in query.all()]


@router.post("/{task_id}/send")
def mark_reminder_sent(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(FollowTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="follow_task_not_found")
    task.status = "已发送"
    task.result = "已发送"
    task.due_date = task.due_date or datetime.utcnow()
    db.commit()
    db.refresh(task)
    return _task_payload(task)
