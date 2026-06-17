from datetime import timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import Appointment


class SchedulerAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def create_appointment(
        self,
        store_id: int,
        customer_id: int,
        pet_id: int,
        service_type: str,
        start_time,
        duration_minutes: int = 60,
        staff_id: int | None = None,
    ) -> dict:
        end_time = start_time + timedelta(minutes=duration_minutes)
        conflict = (
            self.db_session.query(Appointment)
            .filter(
                Appointment.store_id == store_id,
                Appointment.status.in_(["待确认", "已确认"]),
                and_(Appointment.start_time < end_time, Appointment.end_time > start_time),
            )
            .first()
        )
        if conflict is not None:
            return {"created": False, "error": "appointment_conflict"}

        appointment = Appointment(
            store_id=store_id,
            customer_id=customer_id,
            pet_id=pet_id,
            service_type=service_type,
            start_time=start_time,
            end_time=end_time,
            staff_id=staff_id,
            status="已确认",
        )
        self.db_session.add(appointment)
        self.db_session.commit()
        return {"created": True, "appointment_id": appointment.id}
