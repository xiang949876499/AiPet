from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import Customer, Pet, Product, SampleTrial
from web.routes.deps import get_db

router = APIRouter()


@router.get("")
def list_samples(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = db.query(SampleTrial).order_by(SampleTrial.receive_time.desc(), SampleTrial.id.desc())
    if status == "converted":
        query = query.filter(SampleTrial.converted.is_(True))
    elif status in {"pending", "待反馈"}:
        query = query.filter(SampleTrial.converted.is_(False))
    trials = query.all()
    customer_ids = {trial.customer_id for trial in trials}
    pet_ids = {trial.pet_id for trial in trials}
    product_ids = {trial.product_id for trial in trials if trial.product_id is not None}
    customers = {
        customer.id: customer.name
        for customer in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
    } if customer_ids else {}
    pets = {pet.id: pet.name for pet in db.query(Pet).filter(Pet.id.in_(pet_ids)).all()} if pet_ids else {}
    products = {
        product.id: product.name
        for product in db.query(Product).filter(Product.id.in_(product_ids)).all()
    } if product_ids else {}
    return [
        {
            "id": trial.id,
            "customer_id": trial.customer_id,
            "customer_name": customers.get(trial.customer_id, ""),
            "pet_id": trial.pet_id,
            "pet_name": pets.get(trial.pet_id, ""),
            "product_id": trial.product_id,
            "product_name": products.get(trial.product_id, "") if trial.product_id else "",
            "receive_time": trial.receive_time.isoformat(),
            "follow_time": trial.follow_time.isoformat() if trial.follow_time else None,
            "feedback": trial.feedback,
            "converted": trial.converted,
            "converted_amount": float(trial.converted_amount or 0),
        }
        for trial in trials
    ]
