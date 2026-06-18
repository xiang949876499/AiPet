import os
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from agents.reminder import ReminderAgent
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Customer, FollowTask, PushTask
from core.wecom_client import WeComClient
from services.wecom_oauth import bind_wecom_staff

templates = Jinja2Templates(directory="web/templates")


def _env_value(name: str, fallback: str = "") -> str:
    return os.getenv(name, fallback)


def _env_enabled(name: str, fallback: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return fallback
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _create_wecom_client() -> WeComClient:
    return WeComClient(
        corp_id=_env_value("WECOM_CORP_ID", settings.wecom_corp_id),
        app_secret=_env_value("WECOM_APP_SECRET", settings.wecom_app_secret),
        agent_id=_env_value("WECOM_AGENT_ID", settings.wecom_agent_id),
    )


def create_app(wecom_client_factory=_create_wecom_client) -> FastAPI:
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

    @app.get("/wecom/oauth/start")
    def wecom_oauth_start():
        if not _env_enabled("WECOM_OAUTH_ENABLED", settings.wecom_oauth_enabled):
            raise HTTPException(status_code=503, detail="企业微信登录未启用")

        corp_id = _env_value("WECOM_CORP_ID", settings.wecom_corp_id)
        agent_id = _env_value("WECOM_AGENT_ID", settings.wecom_agent_id)
        redirect_uri = _env_value("WECOM_REDIRECT_URI", settings.wecom_redirect_uri)
        if not corp_id or not agent_id or not redirect_uri:
            raise HTTPException(status_code=503, detail="企业微信登录未配置")

        params = {
            "appid": corp_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snsapi_base",
            "agentid": agent_id,
            "state": "aipet",
        }
        return RedirectResponse(f"https://open.weixin.qq.com/connect/oauth2/authorize?{urlencode(params)}#wechat_redirect")

    @app.get("/wecom/oauth/callback")
    def wecom_oauth_callback(code: str):
        if not _env_enabled("WECOM_OAUTH_ENABLED", settings.wecom_oauth_enabled):
            raise HTTPException(status_code=503, detail="企业微信登录未启用")

        init_db()
        client = wecom_client_factory()
        userid = client.get_oauth_userid(code)
        if not userid:
            raise HTTPException(status_code=401, detail="企业微信登录失败")

        detail = client.get_user_detail(userid) or {}
        session = SessionLocal()
        try:
            staff = bind_wecom_staff(
                session,
                corp_id=client.corp_id,
                userid=userid,
                name=detail.get("name") or "",
                avatar=detail.get("avatar") or "",
            )
        finally:
            session.close()

        response = RedirectResponse("/")
        response.set_cookie("aipet_staff_id", str(staff.id), httponly=True, samesite="lax")
        response.set_cookie("aipet_wecom_userid", userid, httponly=True, samesite="lax")
        return response

    return app


app = create_app()
