from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agents.reminder import ReminderAgent
from app.database import SessionLocal, init_db
from app.models import Customer, FollowTask, PushTask

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

    @app.get("/push-tasks", response_class=HTMLResponse)
    def push_tasks(request: Request):
        init_db()
        session = SessionLocal()
        try:
            tasks = session.query(PushTask).order_by(PushTask.created_at.desc()).all()
            status_labels = {
                "pending": "待确认",
                "approved": "已确认",
                "sent": "已发送",
                "failed": "发送失败",
                "skipped": "已跳过",
                "cancelled": "已取消",
            }
            return templates.TemplateResponse(
                request,
                "push_tasks.html",
                {
                    "tasks": tasks,
                    "status_labels": status_labels,
                    "app_name": "宠物店 AI 复购提醒助手",
                },
            )
        finally:
            session.close()

    return app


app = create_app()
