from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import FollowTask
from core.llm import LLMClient
from web.routes.deps import get_db

router = APIRouter()

MAX_FRIENDLY_MESSAGE_LENGTH = 180

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


def _friendly_message_prompt(task: FollowTask) -> str:
    customer_name = task.customer.name if task.customer else "客户"
    pet_name = task.pet.name if task.pet else "宠物"
    return f"""你是宠物门店的一线客服/店长助手。请根据任务信息，生成一条可直接发给客户的微信话术。
要求：
- 只输出一条可直接复制发送给客户的微信话术，不要标题、编号或解释
- 先给客户一个明确的预约理由，不要只重复“有一阵子”
- 用“过程 + 效果 + 风险降低”解释洗护价值，比如基础洗护、吹干、梳理、毛发或脚底状态查看
- 给一个低压力的下一步选择，比如今天/明天哪个时间方便
- 120 字以内
- 必须包含客户称呼和宠物名字
- 不要制造焦虑，不要涉及医疗诊断，不要建议用药

客户：{customer_name}
宠物：{pet_name}
任务类型：{task.task_type}
触发原因：{task.reason}
建议动作：{task.suggested_action}
当前话术：{task.ai_message or ""}
"""


def _days_since_from_reason(reason: str) -> str:
    match = re.search(r"距今\s*(\d+)\s*天", reason or "")
    return f"距今 {match.group(1)} 天" if match else "已经到洗护周期"


def _fallback_friendly_message(task: FollowTask) -> str:
    customer_name = task.customer.name if task.customer else "您"
    pet_name = task.pet.name if task.pet else "宝贝"
    task_type = (task.task_type or "").lower()
    reason = task.reason or ""

    if "wash" in task_type or "洗" in (task.task_type or "") or "洗护" in reason:
        days_since = _days_since_from_reason(reason)
        return (
            f"{customer_name}，{pet_name}上次洗护{days_since}，可以安排一次基础洗护，"
            "充分吹干梳理，顺便看一下毛发和脚底状态。您看今天或明天哪个时间方便？"
        )
    if "content" in task_type or "内容" in (task.task_type or ""):
        return (
            f"{customer_name}，今天店里准备了和{pet_name}相关的小内容，"
            "如果您愿意，我们可以帮您整理成更好看的朋友圈素材。"
        )
    return (
        f"{customer_name}，想和您确认一下{pet_name}最近的情况。"
        "您方便的时候回我一句就好，我帮您把后续安排顺手记上。"
    )


def _clean_message(message: str | None) -> str:
    cleaned = " ".join((message or "").strip().split())
    if len(cleaned) <= MAX_FRIENDLY_MESSAGE_LENGTH:
        return cleaned
    return cleaned[: MAX_FRIENDLY_MESSAGE_LENGTH - 1].rstrip("，。,. ") + "。"


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


@router.post("/{task_id}/skip")
def skip_reminder(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(FollowTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="follow_task_not_found")
    task.status = "已跳过"
    task.result = "已跳过"
    db.commit()
    db.refresh(task)
    return _task_payload(task)


@router.post("/{task_id}/update-message")
def update_reminder_message(task_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    task = db.get(FollowTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="follow_task_not_found")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message_required")
    task.ai_message = message
    db.commit()
    db.refresh(task)
    return _task_payload(task)


@router.post("/{task_id}/friendly-message")
def generate_friendly_message(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(FollowTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="follow_task_not_found")

    generated = LLMClient().generate(_friendly_message_prompt(task))
    message = _clean_message(generated) or _fallback_friendly_message(task)

    task.ai_message = _clean_message(message)
    db.commit()
    db.refresh(task)
    return _task_payload(task)
