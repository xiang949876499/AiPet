import os
import hashlib
import json
import platform
import secrets
import tempfile
import uuid
from datetime import datetime
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agents.content import ContentAgent
from agents.growth import ActivityPlanAgent, AdvisorAgent, StoreAuditAgent, WeeklyReportAgent
from agents.reminder import ReminderAgent
from agents.review import ReviewAgent
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import (
    Appointment,
    ContentItem,
    Customer,
    FollowTask,
    Pet,
    Product,
    PushTask,
    SampleTrial,
    ServiceRecord,
    Staff,
    Store,
)
from analytics.dashboard import build_tiered_dashboard
from content_engine.calendar import build_content_calendar
from core.wecom_client import WeComClient
from licensing.client import LicenseClient
from licensing.middleware import LicenseMiddleware
from licensing.storage import LicenseStorage
from outreach.confirm_flow import confirm_message, get_pending_confirmations, reject_message
from outreach.engine import dispatch_outreach
from outreach.rules import _ensure_default_rules
from services.customer_import import CUSTOMER_IMPORT_TEMPLATE, import_customers_from_csv, preview_customers_from_csv
from services.credits import consume_credit_task
from services.ops_dashboard import build_customer_opportunities, build_ops_metrics, build_subscription_snapshot
from services.subscriptions import ensure_store_subscription
from services.push_tasks import create_internal_push_task
from services.weekly_plan import build_7_day_ops_plan
from services.wecom_push import send_push_task
from services.wecom_oauth import bind_wecom_staff
from web.routes import appointments, customers, reminders, samples

templates = Jinja2Templates(directory="web/templates")

AUTH_EXEMPT_PATHS = {
    "/login",
    "/activate",
    "/favicon.ico",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


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


def _admin_session_token() -> str:
    secret = _env_value("AIPET_ADMIN_PASSWORD", "admin")
    return hashlib.sha256(f"aipet-admin:{secret}".encode("utf-8")).hexdigest()


def _machine_id() -> str:
    raw = f"{platform.node()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _license_client() -> LicenseClient:
    return LicenseClient(base_url=_env_value("AIPET_LICENSE_SERVER_URL", "https://license.aipet.local"))


def _is_auth_exempt(path: str) -> bool:
    return path in AUTH_EXEMPT_PATHS or path.startswith("/static") or path.startswith("/activate")


def _form_int(value) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _import_result_from_query(request: Request) -> dict | None:
    keys = ("created_customers", "updated_customers", "created_pets", "skipped")
    if not any(key in request.query_params for key in keys):
        return None
    return {key: _form_int(request.query_params.get(key)) for key in keys}


CUSTOMER_FILTER_LABELS = {
    "all": "全部",
    "pending": "待跟进",
    "dnd": "免打扰",
    "due": "最近到店超期",
}


def _customer_list_path(active_filter: str, params: dict | None = None) -> str:
    query = {}
    if active_filter in CUSTOMER_FILTER_LABELS and active_filter != "all":
        query["filter"] = active_filter
    if params:
        query.update({key: value for key, value in params.items() if value is not None})
    return f"/customers?{urlencode(query)}" if query else "/customers"


def _form_int_list(form, field_name: str) -> list[int]:
    raw_values = form.getlist(field_name) if hasattr(form, "getlist") else []
    values = []
    for raw_value in raw_values:
        value = _form_int(raw_value)
        if value:
            values.append(value)
    return values


def create_app(wecom_client_factory=_create_wecom_client) -> FastAPI:
    app = FastAPI(title="宠物店 AI 复购提醒助手")
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    app.add_middleware(LicenseMiddleware)
    app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
    app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])
    app.include_router(reminders.router, prefix="/api/reminders", tags=["reminders"])
    app.include_router(samples.router, prefix="/api/samples", tags=["samples"])

    @app.middleware("http")
    async def local_auth_guard(request: Request, call_next):
        if not _env_enabled("AIPET_AUTH_ENABLED", False) or _is_auth_exempt(request.url.path):
            return await call_next(request)
        session_token = request.cookies.get("aipet_admin_session", "")
        if secrets.compare_digest(session_token, _admin_session_token()):
            return await call_next(request)
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "app_name": "宠物店 AI 管家",
                "error": "",
                "next_path": request.query_params.get("next", "/"),
            },
        )

    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(request: Request):
        form = await request.form()
        password = str(form.get("password", ""))
        next_path = str(form.get("next", "/") or "/")
        expected = _env_value("AIPET_ADMIN_PASSWORD", "admin")
        if not secrets.compare_digest(password, expected):
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "app_name": "宠物店 AI 管家",
                    "error": "密码不正确",
                    "next_path": next_path,
                },
                status_code=401,
            )
        response = RedirectResponse(next_path if next_path.startswith("/") else "/", status_code=303)
        response.set_cookie("aipet_admin_session", _admin_session_token(), httponly=True, samesite="lax")
        return response

    @app.post("/logout")
    def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("aipet_admin_session")
        return response

    @app.get("/activate", response_class=HTMLResponse)
    def activate_page(request: Request):
        return templates.TemplateResponse(
            request,
            "activate.html",
            {
                "app_name": "宠物店 AI 管家",
                "error": "",
                "reason": request.query_params.get("reason", ""),
                "status": LicenseStorage().get_status(),
            },
        )

    @app.post("/activate", response_class=HTMLResponse)
    async def activate_submit(request: Request):
        form = await request.form()
        code = str(form.get("code", "")).strip()
        store_name = str(form.get("store_name", "")).strip()
        phone = str(form.get("phone", "")).strip()
        client = _license_client()
        result = client.activate(code, store_name, phone, _machine_id())
        if result is None:
            return templates.TemplateResponse(
                request,
                "activate.html",
                {
                    "app_name": "宠物店 AI 管家",
                    "error": client.last_error or "激活失败，请检查激活码或网络",
                    "reason": "",
                    "status": LicenseStorage().get_status(),
                },
                status_code=400,
            )
        LicenseStorage().save_token(result["token"], result["plan_code"], result["expires_at"])
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("aipet_license_unlocked", "1", httponly=True, samesite="lax")
        return response

    @app.get("/onboarding", response_class=HTMLResponse)
    def onboarding_page(request: Request):
        return templates.TemplateResponse(
            request,
            "onboarding.html",
            {"app_name": "首次设置"},
        )

    @app.post("/activate/trial")
    def activate_trial():
        LicenseStorage().create_trial_token()
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("aipet_license_unlocked", "1", httponly=True, samesite="lax")
        return response

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
                        "action_recommendations": [],
                        "ai_metrics": {},
                        "conversion_funnel": None,
                        "customer_health": None,
                        "subscription": {
                            "plan_name": "未配置",
                            "remaining_ai_quota": 0,
                            "features": [],
                            "status_label": "未配置",
                            "trial_days_left": 0,
                        },
                        "store": None,
                        "app_name": "宠物店 AI 运营 Agent",
                    },
                )
            subscription = ensure_store_subscription(session, store.id)
            plan_code = subscription.plan.code if subscription.plan else "starter"
            ReminderAgent(session).execute({})
            ContentAgent(session).execute({"store_id": store.id})
            dashboard_data = build_tiered_dashboard(session, store.id, plan_code)
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
                    "ai_metrics": dashboard_data["metrics"],
                    "ops_metrics": dashboard_data["ops_metrics"],
                    "subscription": dashboard_data["subscription"],
                    "opportunities": dashboard_data["opportunities"],
                    "action_recommendations": dashboard_data["action_recommendations"],
                    "conversion_funnel": dashboard_data.get("conversion_funnel"),
                    "customer_health": dashboard_data.get("customer_health"),
                    "weekly_plan": build_7_day_ops_plan(session, store.id),
                    "content_items": content_items,
                    "tasks": tasks,
                    "store": store,
                    "app_name": "宠物店 AI 运营 Agent",
                },
            )
        finally:
            session.close()

    @app.get("/push-tasks", response_class=HTMLResponse)
    def push_tasks(request: Request):
        return RedirectResponse("/outreach#send", status_code=302)

    @app.get("/outreach", response_class=HTMLResponse)
    def outreach_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            ReminderAgent(session).execute({})
            tasks = (
                session.query(FollowTask)
                .order_by(FollowTask.created_at.desc(), FollowTask.id.desc())
                .all()
            )
            push_tasks = (
                session.query(PushTask)
                .order_by(PushTask.created_at.desc(), PushTask.id.desc())
                .all()
            )
            confirmations = get_pending_confirmations(session, store.id) if store else []
            pending_script_count = len([task for task in tasks if task.status == "待处理" and task.ai_message])
            pending_generation_count = len([task for task in tasks if task.status == "待处理" and not task.ai_message])
            pending_send_count = len([task for task in push_tasks if task.status in {"pending", "approved"}])
            sent_count = len([task for task in tasks if task.status in {"已发送", "已完成"}])
            return templates.TemplateResponse(
                request,
                "outreach.html",
                {
                    "app_name": "客户触达",
                    "tasks": tasks,
                    "push_tasks": push_tasks,
                    "confirmations": confirmations,
                    "counts": {
                        "pending_generation": pending_generation_count,
                        "pending_confirm": len(confirmations),
                        "pending_send": pending_send_count,
                        "sent": sent_count,
                        "all": len(tasks) + len(push_tasks),
                    },
                },
            )
        finally:
            session.close()

    @app.post("/push-tasks/{task_id}/approve")
    def push_task_approve(task_id: int):
        init_db()
        session = SessionLocal()
        try:
            task = session.get(PushTask, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="push_task_not_found")
            if task.status == "pending":
                task.status = "approved"
                session.commit()
            return RedirectResponse("/outreach#send", status_code=303)
        finally:
            session.close()

    @app.post("/push-tasks/{task_id}/skip")
    def push_task_skip(task_id: int):
        init_db()
        session = SessionLocal()
        try:
            task = session.get(PushTask, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="push_task_not_found")
            task.status = "skipped"
            session.commit()
            return RedirectResponse("/outreach#send", status_code=303)
        finally:
            session.close()

    @app.post("/push-tasks/{task_id}/send")
    def push_task_send(task_id: int):
        init_db()
        session = SessionLocal()
        try:
            task = session.get(PushTask, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="push_task_not_found")
            if not _env_enabled("WECOM_INTERNAL_NOTIFY_ENABLED", settings.wecom_internal_notify_enabled):
                task.status = "failed"
                task.error_message = "企业微信真实发送未启用，请先配置 WECOM_INTERNAL_NOTIFY_ENABLED=true"
                session.commit()
            else:
                send_push_task(session, task_id, wecom_client_factory())
            return RedirectResponse("/outreach#send", status_code=303)
        finally:
            session.close()

    @app.get("/customers", response_class=HTMLResponse)
    def customers_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            active_filter = request.query_params.get("filter", "all")
            if active_filter not in CUSTOMER_FILTER_LABELS:
                active_filter = "all"
            global_search = request.query_params.get("global_search", "").strip()

            records = session.query(Customer).order_by(Customer.id.asc()).all()
            pending_customer_ids = {
                customer_id
                for (customer_id,) in (
                    session.query(FollowTask.customer_id)
                    .filter(FollowTask.status == "待处理")
                    .distinct()
                    .all()
                )
            }

            latest_records = {}
            service_records = (
                session.query(ServiceRecord)
                .join(Pet, ServiceRecord.pet_id == Pet.id)
                .filter(ServiceRecord.service_type.in_(["洗护", "美容"]))
                .order_by(ServiceRecord.service_time.desc())
                .all()
            )
            for service_record in service_records:
                latest_records.setdefault(service_record.pet_id, service_record)

            now = datetime.utcnow()
            due_customer_ids = {
                service_record.customer_id
                for service_record in latest_records.values()
                if service_record.pet
                and (now - service_record.service_time).days >= service_record.pet.care_cycle_days
            }

            if active_filter == "pending":
                records = [customer for customer in records if customer.id in pending_customer_ids]
            elif active_filter == "dnd":
                records = [customer for customer in records if customer.do_not_disturb]
            elif active_filter == "due":
                records = [customer for customer in records if customer.id in due_customer_ids]

            if global_search:
                needle = global_search.lower()
                records = [
                    customer
                    for customer in records
                    if needle
                    in " ".join(
                        [
                            customer.name or "",
                            customer.phone or "",
                            customer.wechat_name or "",
                            *[pet.name or "" for pet in customer.pets],
                        ]
                    ).lower()
                ]

            customers_data = [
                {
                    "id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "wechat_name": customer.wechat_name,
                    "visit_count": customer.visit_count,
                    "last_visit_time": customer.last_visit_time,
                    "do_not_disturb": customer.do_not_disturb,
                    "has_pending_task": customer.id in pending_customer_ids,
                    "is_due": customer.id in due_customer_ids,
                    "pet_names": [pet.name for pet in customer.pets],
                }
                for customer in records
            ]
            return templates.TemplateResponse(
                request,
                "customers.html",
                {
                    "customers": customers_data,
                    "active_filter": active_filter,
                    "filter_label": CUSTOMER_FILTER_LABELS[active_filter],
                    "global_search": global_search,
                    "filters": CUSTOMER_FILTER_LABELS,
                    "batch_action": request.query_params.get("batch_action", ""),
                    "batch_count": _form_int(request.query_params.get("batch_count")),
                    "batch_error": request.query_params.get("batch_error", ""),
                    "app_name": "宠物店 AI 复购提醒助手",
                },
            )
        finally:
            session.close()

    @app.post("/customers/batch")
    async def customers_batch_action(request: Request):
        form = await request.form()
        active_filter = str(form.get("return_filter", "all"))
        if active_filter not in CUSTOMER_FILTER_LABELS:
            active_filter = "all"
        customer_ids = _form_int_list(form, "customer_ids")
        if not customer_ids:
            return RedirectResponse(
                _customer_list_path(active_filter, {"batch_error": "no_selection"}),
                status_code=303,
            )

        action = str(form.get("action", ""))
        init_db()
        session = SessionLocal()
        try:
            tasks = (
                session.query(FollowTask)
                .filter(FollowTask.customer_id.in_(customer_ids), FollowTask.status == "待处理")
                .order_by(FollowTask.created_at.asc(), FollowTask.id.asc())
                .all()
            )
            if not tasks:
                return RedirectResponse(
                    _customer_list_path(active_filter, {"batch_error": "no_pending_tasks"}),
                    status_code=303,
                )

            if action == "mark_sent":
                now = datetime.utcnow()
                for task in tasks:
                    task.status = "已发送"
                    task.result = "已发送"
                    task.due_date = task.due_date or now
                session.commit()
                return RedirectResponse(
                    _customer_list_path(
                        active_filter,
                        {"batch_action": "mark_sent", "batch_count": len(tasks)},
                    ),
                    status_code=303,
                )

            if action == "push_internal":
                staff = (
                    session.query(Staff)
                    .filter(Staff.wecom_userid.is_not(None))
                    .order_by(Staff.id.asc())
                    .first()
                )
                if staff is None:
                    return RedirectResponse(
                        _customer_list_path(active_filter, {"batch_error": "no_staff"}),
                        status_code=303,
                    )

                created = 0
                for task in tasks:
                    existing_push = (
                        session.query(PushTask)
                        .filter(
                            PushTask.follow_task_id == task.id,
                            PushTask.status.in_(["pending", "approved", "sent"]),
                        )
                        .first()
                    )
                    if existing_push:
                        continue
                    create_internal_push_task(session, task.id, staff.id)
                    created += 1
                return RedirectResponse(
                    _customer_list_path(
                        active_filter,
                        {"batch_action": "push_internal", "batch_count": created},
                    ),
                    status_code=303,
                )

            raise HTTPException(status_code=400, detail="unknown_batch_action")
        finally:
            session.close()

    @app.get("/customers/{customer_id:int}", response_class=HTMLResponse)
    def customer_detail_page(customer_id: int, request: Request):
        init_db()
        session = SessionLocal()
        try:
            customer = session.get(Customer, customer_id)
            if customer is None:
                raise HTTPException(status_code=404, detail="customer_not_found")
            pets = (
                session.query(Pet)
                .filter_by(customer_id=customer.id)
                .order_by(Pet.id.asc())
                .all()
            )
            service_records = (
                session.query(ServiceRecord)
                .filter_by(customer_id=customer.id)
                .order_by(ServiceRecord.service_time.desc())
                .limit(20)
                .all()
            )
            follow_tasks = (
                session.query(FollowTask)
                .filter_by(customer_id=customer.id)
                .order_by(FollowTask.created_at.desc())
                .limit(20)
                .all()
            )
            pet_names = {pet.id: pet.name for pet in pets}
            return templates.TemplateResponse(
                request,
                "customer_detail.html",
                {
                    "customer": customer,
                    "pets": pets,
                    "service_records": service_records,
                    "follow_tasks": follow_tasks,
                    "pet_names": pet_names,
                    "saved": request.query_params.get("saved", ""),
                    "app_name": "客户档案",
                },
            )
        finally:
            session.close()

    @app.post("/customers/{customer_id:int}/profile")
    async def customer_profile_update(customer_id: int, request: Request):
        form = await request.form()
        init_db()
        session = SessionLocal()
        try:
            customer = session.get(Customer, customer_id)
            if customer is None:
                raise HTTPException(status_code=404, detail="customer_not_found")
            customer.tags = str(form.get("tags", "")).strip() or None
            customer.note = str(form.get("note", "")).strip() or None
            customer.do_not_disturb = form.get("do_not_disturb") == "on"
            session.commit()
            return RedirectResponse(f"/customers/{customer_id}?saved=profile", status_code=303)
        finally:
            session.close()

    @app.get("/customers/import", response_class=HTMLResponse)
    def customers_import_page(request: Request):
        return templates.TemplateResponse(
            request,
            "customers_import.html",
            {
                "app_name": "客户数据导入",
                "result": _import_result_from_query(request),
                "preview": None,
                "error": request.query_params.get("error", ""),
            },
        )

    @app.get("/customers/import/template")
    def customers_import_template():
        return Response(
            "\ufeff" + CUSTOMER_IMPORT_TEMPLATE,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=customers-template.csv"},
        )

    @app.post("/customers/import/preview", response_class=HTMLResponse)
    async def customers_import_preview(request: Request):
        form = await request.form()
        upload = form.get("csv_file")
        if not upload or not getattr(upload, "filename", "") or not hasattr(upload, "read"):
            return RedirectResponse("/customers/import?error=missing_file", status_code=303)
        content = await upload.read()
        if not content:
            return RedirectResponse("/customers/import?error=empty_file", status_code=303)

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            return templates.TemplateResponse(
                request,
                "customers_import.html",
                {
                    "app_name": "客户数据导入",
                    "result": None,
                    "preview": preview_customers_from_csv(temp_path),
                    "error": "",
                },
            )
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    @app.post("/customers/import", response_class=HTMLResponse)
    async def customers_import_upload(request: Request):
        form = await request.form()
        upload = form.get("csv_file")
        if not upload or not getattr(upload, "filename", "") or not hasattr(upload, "read"):
            return RedirectResponse("/customers/import?error=missing_file", status_code=303)
        content = await upload.read()
        if not content:
            return RedirectResponse("/customers/import?error=empty_file", status_code=303)

        init_db()
        session = SessionLocal()
        temp_path = ""
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store is None:
                return RedirectResponse("/customers/import?error=no_store", status_code=303)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            result = import_customers_from_csv(session, store.id, temp_path)
            return RedirectResponse(f"/customers/import?{urlencode(result)}", status_code=303)
        finally:
            session.close()
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    @app.post("/customers/import/generate-reminders")
    def customers_import_generate_reminders():
        init_db()
        session = SessionLocal()
        try:
            ReminderAgent(session).execute({})
            return RedirectResponse("/outreach?generated=1", status_code=303)
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
        return RedirectResponse("/outreach", status_code=302)

    @app.post("/reminders/{task_id}/mark-sent")
    def reminder_mark_sent(task_id: int):
        init_db()
        session = SessionLocal()
        try:
            task = session.get(FollowTask, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="follow_task_not_found")
            task.status = "已发送"
            task.result = "已发送"
            task.due_date = task.due_date or datetime.utcnow()
            session.commit()
            return RedirectResponse("/outreach", status_code=303)
        finally:
            session.close()

    @app.post("/reminders/{task_id}/push-internal")
    def reminder_create_internal_push(task_id: int):
        init_db()
        session = SessionLocal()
        try:
            task = session.get(FollowTask, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="follow_task_not_found")
            staff = (
                session.query(Staff)
                .filter(Staff.store_id == task.store_id, Staff.wecom_userid.is_not(None))
                .order_by(Staff.id.asc())
                .first()
            )
            if staff is None:
                raise HTTPException(status_code=400, detail="no_staff_with_wecom_userid")
            create_internal_push_task(session, task_id, staff.id)
            return RedirectResponse("/outreach#send", status_code=303)
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

    @app.get("/license", response_class=HTMLResponse)
    def license_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            subscription = build_subscription_snapshot(session, store.id) if store else {}
            return templates.TemplateResponse(
                request,
                "license_info.html",
                {
                    "subscription": subscription,
                    "local_license": LicenseStorage().get_status(),
                    "app_name": "授权信息",
                },
            )
        finally:
            session.close()

    @app.get("/outreach/confirm", response_class=HTMLResponse)
    def outreach_confirm_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            messages = get_pending_confirmations(session, store.id) if store else []
            return templates.TemplateResponse(
                request,
                "outreach_confirm.html",
                {"messages": messages, "app_name": "触达确认"},
            )
        finally:
            session.close()

    @app.post("/outreach/confirm/{log_id}")
    def outreach_confirm_action(log_id: int):
        init_db()
        session = SessionLocal()
        try:
            confirm_message(session, log_id)
            return RedirectResponse("/outreach/confirm", status_code=303)
        finally:
            session.close()

    @app.post("/outreach/reject/{log_id}")
    def outreach_reject_action(log_id: int):
        init_db()
        session = SessionLocal()
        try:
            reject_message(session, log_id, "Rejected from web")
            return RedirectResponse("/outreach/confirm", status_code=303)
        finally:
            session.close()

    @app.get("/content/calendar", response_class=HTMLResponse)
    def content_calendar_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            items = build_content_calendar(session, store.id) if store else []
            content_items = (
                session.query(ContentItem)
                .filter_by(store_id=store.id)
                .order_by(ContentItem.created_at.desc())
                .limit(12)
                .all()
                if store
                else []
            )
            return templates.TemplateResponse(
                request,
                "content_calendar.html",
                {"items": items, "content_items": content_items, "app_name": "内容日历"},
            )
        finally:
            session.close()

    @app.post("/content/generate")
    def content_generate_action():
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store:
                ContentAgent(session).execute({"store_id": store.id})
            return RedirectResponse("/content/calendar", status_code=303)
        finally:
            session.close()

    @app.post("/content/{item_id}/publish")
    async def content_publish_action(item_id: int, request: Request):
        form = await request.form()
        init_db()
        session = SessionLocal()
        try:
            item = session.get(ContentItem, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="content_item_not_found")
            interactions = {
                "likes": _form_int(form.get("likes")),
                "comments": _form_int(form.get("comments")),
                "shares": _form_int(form.get("shares")),
                "consultations": _form_int(form.get("consultations")),
            }
            item.status = "published"
            item.published_at = datetime.utcnow()
            item.interaction_data = json.dumps(interactions, ensure_ascii=False)
            session.commit()
            return RedirectResponse("/content/calendar", status_code=303)
        finally:
            session.close()

    @app.get("/audit", response_class=HTMLResponse)
    def audit_page(request: Request):
        return templates.TemplateResponse(
            request,
            "audit.html",
            {"app_name": "门店营销体检报告", "form": {}, "report": ""},
        )

    @app.post("/audit", response_class=HTMLResponse)
    async def audit_generate(request: Request):
        form = await request.form()
        payload = {
            "store_name": str(form.get("store_name", "")).strip(),
            "city": str(form.get("city", "")).strip(),
            "district": str(form.get("district", "")).strip(),
            "services": str(form.get("services", "")).strip(),
            "avg_order_value": str(form.get("avg_order_value", "")).strip(),
        }
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store and not consume_credit_task(session, store.id, "store_audit"):
                return templates.TemplateResponse(
                    request,
                    "audit.html",
                    {"app_name": "门店营销体检报告", "form": payload, "report": "", "credit_error": "Credit 余额不足，暂时不能生成体检报告。"},
                    status_code=402,
                )
            result = StoreAuditAgent(session).execute(payload)
            return templates.TemplateResponse(
                request,
                "audit.html",
                {"app_name": "门店营销体检报告", "form": payload, "report": result["report"], "credit_error": ""},
            )
        finally:
            session.close()

    @app.get("/activity", response_class=HTMLResponse)
    def activity_page(request: Request):
        return templates.TemplateResponse(
            request,
            "activity.html",
            {"app_name": "活动方案生成器", "form": {}, "plan": ""},
        )

    @app.post("/activity", response_class=HTMLResponse)
    async def activity_generate(request: Request):
        form = await request.form()
        payload = {
            "activity_type": str(form.get("activity_type", "")).strip(),
            "target": str(form.get("target", "")).strip(),
            "offer": str(form.get("offer", "")).strip(),
            "duration": str(form.get("duration", "")).strip(),
        }
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store and not consume_credit_task(session, store.id, "activity_plan"):
                return templates.TemplateResponse(
                    request,
                    "activity.html",
                    {"app_name": "活动方案生成器", "form": payload, "plan": "", "credit_error": "Credit 余额不足，暂时不能生成活动方案。"},
                    status_code=402,
                )
            result = ActivityPlanAgent(session).execute(payload)
            return templates.TemplateResponse(
                request,
                "activity.html",
                {"app_name": "活动方案生成器", "form": payload, "plan": result["plan"], "credit_error": ""},
            )
        finally:
            session.close()

    @app.get("/weekly-report", response_class=HTMLResponse)
    def weekly_report_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store and not consume_credit_task(session, store.id, "weekly_report"):
                return templates.TemplateResponse(
                    request,
                    "weekly_report.html",
                    {"app_name": "每周复盘报告", "report": "Credit 余额不足，暂时不能生成每周复盘报告。"},
                    status_code=402,
                )
            result = WeeklyReportAgent(session).execute({})
            return templates.TemplateResponse(
                request,
                "weekly_report.html",
                {"app_name": "每周复盘报告", "report": result["report"]},
            )
        finally:
            session.close()

    @app.get("/advisor", response_class=HTMLResponse)
    def advisor_page(request: Request):
        return templates.TemplateResponse(
            request,
            "advisor.html",
            {"app_name": "AI 经营顾问", "question": "", "answer": ""},
        )

    @app.post("/advisor", response_class=HTMLResponse)
    async def advisor_answer(request: Request):
        form = await request.form()
        question = str(form.get("question", "")).strip()
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            if store and not consume_credit_task(session, store.id, "advisor_question"):
                return templates.TemplateResponse(
                    request,
                    "advisor.html",
                    {"app_name": "AI 经营顾问", "question": question, "answer": "Credit 余额不足，暂时不能提问。"},
                    status_code=402,
                )
            result = AdvisorAgent(session).execute({"question": question})
            return templates.TemplateResponse(
                request,
                "advisor.html",
                {"app_name": "AI 经营顾问", "question": question, "answer": result["answer"]},
            )
        finally:
            session.close()

    @app.get("/review", response_class=HTMLResponse)
    def review_assist_page(request: Request):
        return templates.TemplateResponse(
            request,
            "review_assist.html",
            {
                "app_name": "点评助手",
                "scenario": "positive",
                "review_text": "",
                "reply": "",
            },
        )

    @app.post("/review", response_class=HTMLResponse)
    async def review_assist_generate(request: Request):
        form = await request.form()
        scenario = str(form.get("scenario", "positive"))
        review_text = str(form.get("review_text", "")).strip()
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            store_name = store.name if store else "本店"
            if store and not consume_credit_task(session, store.id, "review_reply"):
                return templates.TemplateResponse(
                    request,
                    "review_assist.html",
                    {
                        "app_name": "点评助手",
                        "scenario": scenario,
                        "review_text": review_text,
                        "reply": "",
                        "credit_error": "Credit 余额不足，暂时不能生成点评回复。",
                    },
                    status_code=402,
                )
            result = ReviewAgent(session).execute(
                {"scenario": scenario, "review_text": review_text, "store_name": store_name}
            )
            return templates.TemplateResponse(
                request,
                "review_assist.html",
                {
                    "app_name": "点评助手",
                    "scenario": scenario,
                    "review_text": review_text,
                    "reply": result["reply"],
                    "credit_error": "",
                },
            )
        finally:
            session.close()

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        return templates.TemplateResponse(request, "settings.html", {"app_name": "门店设置"})

    @app.get("/settings/rules", response_class=HTMLResponse)
    def rules_config_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            store = session.query(Store).order_by(Store.id.asc()).first()
            rules = _ensure_default_rules(session, store.id) if store else []
            return templates.TemplateResponse(
                request,
                "rules_config.html",
                {"rules": rules, "app_name": "触达规则"},
            )
        finally:
            session.close()

    @app.get("/admin/monitoring", response_class=HTMLResponse)
    def monitoring_page(request: Request):
        init_db()
        session = SessionLocal()
        try:
            health = {
                "stores": session.query(Store).count(),
                "pending_tasks": session.query(FollowTask).count(),
                "license_mode": LicenseStorage().get_status().get("mode"),
                "database": "ok",
            }
            return templates.TemplateResponse(
                request,
                "monitoring.html",
                {"health": health, "app_name": "系统监控"},
            )
        finally:
            session.close()

    return app


app = create_app()
