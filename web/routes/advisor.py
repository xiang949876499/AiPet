from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.growth import AdvisorAgent
from app.models import Store
from services.credits import consume_credit_task
from web.routes.deps import get_db

router = APIRouter()


@router.post("")
def ask_advisor(payload: dict, db: Session = Depends(get_db)) -> dict:
    question = str(payload.get("question") or "").strip()
    category = str(payload.get("category") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question_required")

    store = db.query(Store).order_by(Store.id.asc()).first()
    if store and not consume_credit_task(db, store.id, "advisor_question"):
        raise HTTPException(status_code=402, detail="credit_not_enough")

    return AdvisorAgent(db).execute({"question": question, "category": category})
