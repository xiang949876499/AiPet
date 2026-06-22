from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import Customer
from web.routes.deps import get_db

router = APIRouter()


@router.get("")
def list_customers(db: Session = Depends(get_db)) -> list[dict]:
    customers = db.query(Customer).order_by(Customer.id.asc()).all()
    return [
        {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "wechat_name": customer.wechat_name,
            "source": customer.source,
            "tags": customer.tags,
            "last_visit_time": customer.last_visit_time.isoformat() if customer.last_visit_time else None,
            "visit_count": customer.visit_count,
            "total_amount": float(customer.total_amount or 0),
            "do_not_disturb": customer.do_not_disturb,
            "pet_names": [pet.name for pet in customer.pets],
        }
        for customer in customers
    ]
