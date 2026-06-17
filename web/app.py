from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agents.reminder import ReminderAgent
from app.database import SessionLocal, init_db
from app.models import Customer, FollowTask

templates = Jinja2Templates(directory="web/templates")


def create_app() -> FastAPI:
    app = FastAPI(title="宠物店 AI 复购提醒助手")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        init_db()
        session = SessionLocal()
        try:
            ReminderAgent(session).execute({})
            metrics = {
                "customers": session.query(Customer).count(),
                "pending_tasks": session.query(FollowTask).filter_by(status="待处理").count(),
            }
            tasks = session.query(FollowTask).filter_by(status="待处理").all()
            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {"metrics": metrics, "tasks": tasks, "app_name": "宠物店 AI 复购提醒助手"},
            )
        finally:
            session.close()

    return app


app = create_app()
