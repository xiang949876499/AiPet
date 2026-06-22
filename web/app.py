import os
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from agents.content import ContentAgent
from agents.reminder import ReminderAgent
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Appointment, ContentItem, Customer, FollowTask, Pet, Product, PushTask, SampleTrial, Store
from core.wecom_client import WeComClient
from services.ops_dashboard import build_customer_opportunities, build_ops_metrics, build_subscription_snapshot
from services.subscriptions import ensure_store_subscription
from services.weekly_plan import build_7_day_ops_plan
from services.wecom_oauth import bind_wecom_staff
from web.routes import appointments, customers, reminders, samples

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
    app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
    app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])
    app.include_router(reminders.router, prefix="/api/reminders", tags=["reminders"])
    app.include_router(samples.router, prefix="/api/samples", tags=["samples"])

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store is None:
                return templates.TemplateResponse(
                    request,
                    "dashboard.html",
                    {
                        "metrics": {"customers": 0, "pending_tasks": 0},
                        "ops_metrics": {
                            "weekly_touch_tasks": 0,
                            "weekly_content_items": 0,
                            "monthly_repurchase_customers": 0,
                            "estimated_recovered_revenue": 0,
                        },
                        "tasks": [],
                        "opportunities": [],
                        "content_items": [],
                        "weekly_plan": [],
                        "subscription": {
                            "plan_name": "未配置",
                            "remaining_ai_quota": 0,
                            "features": [],
                            "status_label": "未配置",
                            "trial_days_left": 0,
                        },
                        "app_name": "宠物店 AI 运营 Agent",
                    },
                )
            ensure_store_subscription(session, store.id)
            ReminderAgent(session).execute({})
            ContentAgent(session).execute({"store_id": store.id})
            metrics = {
                "customers": session.query(Customer).count(),
                "pending_tasks": session.query(FollowTask).filter_by(status="待处理").count(),
            }
            tasks = session.query(FollowTask).filter_by(status="待处理").all()
            content_items = (
                session.query(ContentItem)
                .filter_by(store_id=store.id)
                .order_by(ContentItem.scheduled_at.asc().nullslast(), ContentItem.created_at.desc())
                .limit(6)
                .all()
            )
            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "metrics": metrics,
                    "ops_metrics": build_ops_metrics(session, store.id),
                    "subscription": build_subscription_snapshot(session, store.id),
                    "opportunities": build_customer_opportunities(session, store.id),
                    "weekly_plan": build_7_day_ops_plan(session, store.id),
                    "content_items": content_items,
                    "tasks": tasks,
                    "app_name": "宠物店 AI 运营 Agent",
                },
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

    @app.get("/customers", response_class=HTMLResponse)
    def customers_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            records = session.query(Customer).order_by(Customer.id.asc()).all()
            customers_data = [
                {
                    "id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "wechat_name": customer.wechat_name,
                    "visit_count": customer.visit_count,
                    "last_visit_time": customer.last_visit_time,
                    "pet_names": [pet.name for pet in customer.pets],
                }
                for customer in records
            ]
            return templates.TemplateResponse(
                request,
                "customers.html",
                {"customers": customers_data, "app_name": "宠物店 AI 复购提醒助手"},
            )
        finally:
            session.close()

    @app.get("/appointments", response_class=HTMLResponse)
    def appointments_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            records = session.query(Appointment).order_by(Appointment.start_time.asc()).all()
            customers_by_id = {customer.id: customer for customer in session.query(Customer).all()}
            pets_by_id = {pet.id: pet for pet in session.query(Pet).all()}
            appointments_data = [
                {
                    "id": appointment.id,
                    "customer_name": customers_by_id.get(appointment.customer_id).name
                    if customers_by_id.get(appointment.customer_id)
                    else "",
                    "pet_name": pets_by_id.get(appointment.pet_id).name if pets_by_id.get(appointment.pet_id) else "",
                    "service_type": appointment.service_type,
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "status": appointment.status,
                }
                for appointment in records
            ]
            return templates.TemplateResponse(
                request,
                "appointments.html",
                {
                    "appointments": appointments_data,
                    "app_name": "宠物店 AI 复购提醒助手",
                },
            )
        finally:
            session.close()

    @app.get("/reminders", response_class=HTMLResponse)
    def reminders_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            ReminderAgent(session).execute({})
            tasks = session.query(FollowTask).order_by(FollowTask.created_at.desc(), FollowTask.id.desc()).all()
            task_data = [
                {
                    "id": task.id,
                    "customer_name": task.customer.name,
                    "pet_name": task.pet.name,
                    "task_type": task.task_type,
                    "priority": task.priority,
                    "reason": task.reason,
                    "suggested_action": task.suggested_action,
                    "status": task.status,
                    "ai_message": task.ai_message,
                }
                for task in tasks
            ]
            return templates.TemplateResponse(
                request,
                "reminders.html",
                {"tasks": task_data, "app_name": "宠物店 AI 复购提醒助手"},
            )
        finally:
            session.close()

    @app.get("/samples", response_class=HTMLResponse)
    def samples_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            trials = session.query(SampleTrial).order_by(SampleTrial.receive_time.desc(), SampleTrial.id.desc()).all()
            products_by_id = {product.id: product for product in session.query(Product).all()}
            customers_by_id = {customer.id: customer for customer in session.query(Customer).all()}
            pets_by_id = {pet.id: pet for pet in session.query(Pet).all()}
            trials_data = [
                {
                    "id": trial.id,
                    "customer_name": customers_by_id.get(trial.customer_id).name
                    if customers_by_id.get(trial.customer_id)
                    else "",
                    "pet_name": pets_by_id.get(trial.pet_id).name if pets_by_id.get(trial.pet_id) else "",
                    "product_name": products_by_id.get(trial.product_id).name
                    if trial.product_id and products_by_id.get(trial.product_id)
                    else "",
                    "receive_time": trial.receive_time,
                    "feedback": trial.feedback,
                    "converted": trial.converted,
                    "converted_amount": trial.converted_amount,
                }
                for trial in trials
            ]
            return templates.TemplateResponse(
                request,
                "samples.html",
                {
                    "trials": trials_data,
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
