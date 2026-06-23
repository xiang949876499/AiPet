from collections.abc import Generator
from datetime import datetime, timedelta
import secrets

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from models import ActivationCode, ActivationRecord, License


app = FastAPI(title="AIPet License Server")

try:
    from admin.routes import router as admin_router

    app.include_router(admin_router)
except Exception:  # pragma: no cover - keeps single-file local startup resilient
    admin_router = None


class ActivateRequest(BaseModel):
    activation_code: str
    store_name: str
    phone: str = ""
    machine_id: str


class HeartbeatRequest(BaseModel):
    token: str
    machine_id: str = ""


class VerifyRequest(BaseModel):
    token: str
    machine_id: str = ""


class RenewRequest(BaseModel):
    token: str
    renew_code: str


class UpgradeRequest(BaseModel):
    token: str
    upgrade_code: str


def get_session() -> Generator[Session, None, None]:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.post("/activate")
@app.post("/api/activate")
def activate(payload: ActivateRequest, session: Session = Depends(get_session)):
    activation_code = payload.activation_code.strip().upper()
    code = session.query(ActivationCode).filter_by(code=activation_code).first()
    if code is None or code.status == "revoked":
        raise HTTPException(status_code=404, detail="activation code not found")

    existing_license = (
        session.query(License)
        .filter_by(activation_code_id=code.id)
        .order_by(License.id.desc())
        .first()
    )
    if code.status == "used" and existing_license and existing_license.machine_id:
        raise HTTPException(status_code=400, detail="activation code already used")

    token = f"LICENSE-{secrets.token_urlsafe(24)}"
    expires_at = datetime.utcnow() + timedelta(days=code.valid_days)
    if existing_license and existing_license.machine_id is None:
        existing_license.token = token
        existing_license.plan_code = code.plan_code
        existing_license.store_name = payload.store_name
        existing_license.phone = payload.phone
        existing_license.machine_id = payload.machine_id
        existing_license.status = "active"
        existing_license.expires_at = expires_at
        existing_license.last_heartbeat_at = datetime.utcnow()
        license_row = existing_license
    else:
        license_row = License(
            activation_code_id=code.id,
            token=token,
            plan_code=code.plan_code,
            store_name=payload.store_name,
            phone=payload.phone,
            machine_id=payload.machine_id,
            expires_at=expires_at,
            last_heartbeat_at=datetime.utcnow(),
        )
        session.add(license_row)

    code.status = "used"
    session.flush()
    session.add(
        ActivationRecord(
            activation_code_id=code.id,
            license_id=license_row.id,
            machine_id=payload.machine_id,
            event="activate",
        )
    )
    session.commit()
    return {"token": token, "plan_code": code.plan_code, "expires_at": license_row.expires_at.isoformat()}


@app.post("/heartbeat")
@app.post("/api/heartbeat")
def heartbeat(payload: HeartbeatRequest, session: Session = Depends(get_session)):
    license_row = session.query(License).filter_by(token=payload.token).first()
    if license_row is None:
        raise HTTPException(status_code=404, detail="license not found")
    if payload.machine_id and license_row.machine_id and license_row.machine_id != payload.machine_id:
        raise HTTPException(status_code=403, detail="machine mismatch")
    license_row.last_heartbeat_at = datetime.utcnow()
    session.add(ActivationRecord(license_id=license_row.id, machine_id=payload.machine_id, event="heartbeat"))
    session.commit()
    return {
        "ok": True,
        "plan_code": license_row.plan_code,
        "expires_at": license_row.expires_at.isoformat(),
        "status": license_row.status,
    }


@app.post("/api/verify")
def verify(payload: VerifyRequest, session: Session = Depends(get_session)):
    license_row = session.query(License).filter_by(token=payload.token).first()
    if license_row is None:
        return {"valid": False}
    if payload.machine_id and license_row.machine_id and license_row.machine_id != payload.machine_id:
        return {"valid": False, "reason": "machine_mismatch"}
    if license_row.status != "active":
        return {"valid": False, "reason": license_row.status}
    if datetime.utcnow() > license_row.expires_at:
        license_row.status = "expired"
        session.commit()
        return {"valid": False, "reason": "expired"}
    return {
        "valid": True,
        "plan_code": license_row.plan_code,
        "expires_at": license_row.expires_at.isoformat(),
        "status": license_row.status,
    }


@app.post("/api/renew")
def renew_license(payload: RenewRequest, session: Session = Depends(get_session)):
    license_row = session.query(License).filter_by(token=payload.token).first()
    if license_row is None:
        raise HTTPException(status_code=404, detail="license not found")

    renew_code = session.query(ActivationCode).filter_by(code=payload.renew_code.strip().upper()).first()
    if renew_code is None or renew_code.status != "unused":
        raise HTTPException(status_code=400, detail="renew code invalid or already used")

    base_expiry = max(license_row.expires_at, datetime.utcnow())
    license_row.expires_at = base_expiry + timedelta(days=renew_code.valid_days)
    license_row.status = "active"
    renew_code.status = "used"
    session.add(
        ActivationRecord(
            activation_code_id=renew_code.id,
            license_id=license_row.id,
            machine_id=license_row.machine_id or "",
            event="renew",
            detail=f"extended by {renew_code.valid_days}d",
        )
    )
    session.commit()
    return {
        "token": license_row.token,
        "plan_code": license_row.plan_code,
        "expires_at": license_row.expires_at.isoformat(),
    }


@app.post("/api/upgrade")
def upgrade_license(payload: UpgradeRequest, session: Session = Depends(get_session)):
    license_row = session.query(License).filter_by(token=payload.token).first()
    if license_row is None:
        raise HTTPException(status_code=404, detail="license not found")

    upgrade_code = session.query(ActivationCode).filter_by(code=payload.upgrade_code.strip().upper()).first()
    if upgrade_code is None or upgrade_code.status != "unused":
        raise HTTPException(status_code=400, detail="upgrade code invalid or already used")

    old_plan = license_row.plan_code
    license_row.plan_code = upgrade_code.plan_code
    license_row.status = "active"
    upgrade_code.status = "used"
    session.add(
        ActivationRecord(
            activation_code_id=upgrade_code.id,
            license_id=license_row.id,
            machine_id=license_row.machine_id or "",
            event="upgrade",
            detail=f"{old_plan} -> {upgrade_code.plan_code}",
        )
    )
    session.commit()
    return {
        "token": license_row.token,
        "plan_code": license_row.plan_code,
        "expires_at": license_row.expires_at.isoformat(),
    }
