from collections.abc import Generator
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from models import ActivationCode, ActivationRecord, License

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def get_session() -> Generator[Session, None, None]:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.get("", response_class=HTMLResponse)
def admin_index(request: Request, session: Session = Depends(get_session)):
    codes = session.query(ActivationCode).order_by(ActivationCode.id.desc()).limit(50).all()
    licenses = session.query(License).order_by(License.id.desc()).limit(50).all()
    records = session.query(ActivationRecord).order_by(ActivationRecord.id.desc()).limit(50).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "codes": codes,
            "licenses": licenses,
            "records": records,
        },
    )


@router.post("/activation-codes")
def create_activation_codes(plan_code: str, count: int = 1, valid_days: int = 365, session: Session = Depends(get_session)):
    codes = ActivationCode.generate_batch(plan_code, count, valid_days)
    for code in codes:
        session.add(ActivationCode(code=code, plan_code=plan_code, valid_days=valid_days))
    session.commit()
    return {"codes": codes}


@router.post("/licenses/{license_id}/unbind")
def unbind_machine(license_id: int, session: Session = Depends(get_session)):
    license_row = session.get(License, license_id)
    if license_row is None:
        return {"updated": False}
    machine_id = license_row.machine_id or ""
    license_row.machine_id = None
    session.add(ActivationRecord(license_id=license_row.id, machine_id=machine_id, event="unbind"))
    session.commit()
    return {"updated": True}
