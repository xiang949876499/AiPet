from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Customer, FollowTask, Pet, ServiceRecord
from core.prompt_templates import fallback_message


class ReminderAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def execute(self, context: dict) -> dict:
        store_id = context.get("store_id")
        created = 0

        query = (
            self.db_session.query(ServiceRecord)
            .join(Pet, ServiceRecord.pet_id == Pet.id)
            .join(Customer, ServiceRecord.customer_id == Customer.id)
            .filter(ServiceRecord.service_type.in_(["洗护", "美容"]))
        )
        if store_id is not None:
            query = query.filter(ServiceRecord.store_id == store_id)

        latest_records = {}
        for record in query.order_by(ServiceRecord.service_time.desc()).all():
            latest_records.setdefault(record.pet_id, record)

        now = datetime.utcnow()
        for record in latest_records.values():
            pet = record.pet
            customer = record.customer
            if customer.do_not_disturb:
                continue

            days_since = (now - record.service_time).days
            if days_since < pet.care_cycle_days:
                continue

            has_open_task = (
                self.db_session.query(func.count(FollowTask.id))
                .filter(
                    FollowTask.pet_id == pet.id,
                    FollowTask.task_type == "洗护提醒",
                    FollowTask.status.in_(["待处理", "已发送"]),
                )
                .scalar()
            )
            if has_open_task:
                continue

            priority = "高" if days_since >= pet.care_cycle_days + 3 else "中"
            reason = f"{pet.name}上次洗护距今 {days_since} 天，最近 7 天没有预约"
            task = FollowTask(
                store_id=record.store_id,
                customer_id=customer.id,
                pet_id=pet.id,
                task_type="洗护提醒",
                priority=priority,
                reason=reason,
                suggested_action="发送温和预约提醒",
                due_date=now,
                ai_message=fallback_message("洗护提醒", customer.name, pet.name),
            )
            self.db_session.add(task)
            created += 1

        self.db_session.commit()
        return {"created": created}
