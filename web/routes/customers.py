import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.models import Customer, Store
from services.customer_import import CUSTOMER_IMPORT_TEMPLATE, import_customers_from_csv, preview_customers_from_csv
from services.ops_dashboard import build_outreach_queue
from web.routes.deps import get_db

router = APIRouter()


@router.get("/outreach-queue")
def outreach_queue(store_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    store = _get_store(db, store_id)
    return build_outreach_queue(db, store.id)


@router.post("/import/preview")
async def preview_customer_import(csv_file: UploadFile = File(...)) -> dict:
    temp_path = await _save_upload(csv_file)
    try:
        return preview_customers_from_csv(temp_path)
    finally:
        _unlink_temp(temp_path)


@router.post("/import")
async def import_customers_json(csv_file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    store = _get_store(db)
    temp_path = await _save_upload(csv_file)
    try:
        return import_customers_from_csv(db, store.id, temp_path)
    finally:
        _unlink_temp(temp_path)


@router.get("/import/template")
def customer_import_template() -> Response:
    return Response(
        "\ufeff" + CUSTOMER_IMPORT_TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=customers-template.csv"},
    )


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


def _get_store(db: Session, store_id: int | None = None) -> Store:
    if store_id is not None:
        store = db.get(Store, store_id)
    else:
        store = db.query(Store).order_by(Store.id.asc()).first()
    if store is None:
        raise HTTPException(status_code=400, detail="store_not_found")
    return store


async def _save_upload(upload: UploadFile) -> str:
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        temp_file.write(content)
        return temp_file.name


def _unlink_temp(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
