from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import FollowTask, SampleTrial


class SampleAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def execute(self, context: dict) -> dict:
        store_id = context.get("store_id")
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        created = 0

        query = self.db_session.query(SampleTrial).filter(SampleTrial.follow_time.is_(None))
        if store_id is not None:
            query = query.filter(SampleTrial.store_id == store_id)

        for trial in query.all():
            if trial.receive_time > yesterday:
                continue
            task_exists = (
                self.db_session.query(FollowTask)
                .filter(FollowTask.pet_id == trial.pet_id, FollowTask.task_type == "试用装回访")
                .first()
            )
            if task_exists:
                trial.follow_time = now
                continue
            task = FollowTask(
                store_id=trial.store_id,
                customer_id=trial.customer_id,
                pet_id=trial.pet_id,
                task_type="试用装回访",
                priority="中",
                reason="客户昨日领取试用装，需要询问适口性和反馈",
                suggested_action="发送试用装体验关怀话术",
                due_date=now,
                ai_message="想问下昨天带回家的试用装，宝贝有试吃吗？适口性怎么样呀？",
            )
            self.db_session.add(task)
            trial.follow_time = now
            created += 1

        self.db_session.commit()
        return {"created": created}
