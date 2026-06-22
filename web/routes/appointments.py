from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import Appointment, Customer, Pet
from web.routes.deps import get_db

router = APIRouter()


@router.get("")
def list_appointments(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = db.query(Appointment).order_by(Appointment.start_time.asc())
    if status:
        query = query.filter(Appointment.status == status)
    appointments = query.all()
    customer_ids = {appointment.customer_id for appointment in appointments}
    pet_ids = {appointment.pet_id for appointment in appointments}
    customers = {
        customer.id: customer.name
        for customer in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
    } if customer_ids else {}
    pets = {pet.id: pet.name for pet in db.query(Pet).filter(Pet.id.in_(pet_ids)).all()} if pet_ids else {}
    return [
        {
            "id": appointment.id,
            "customer_id": appointment.customer_id,
            "customer_name": customers.get(appointment.customer_id, ""),
            "pet_id": appointment.pet_id,
            "pet_name": pets.get(appointment.pet_id, ""),
            "service_type": appointment.service_type,
            "start_time": appointment.start_time.isoformat(),
            "end_time": appointment.end_time.isoformat() if appointment.end_time else None,
            "status": appointment.status,
            "note": appointment.note,
        }
        for appointment in appointments
    ]
