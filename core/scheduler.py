from agents.reminder import ReminderAgent


def run_reminder_scan(db_session, context: dict | None = None) -> dict:
    return ReminderAgent(db_session).execute(context or {})


def _create_wecom_client():
    from app.config import settings

    if not settings.wecom_corp_id or not settings.wecom_app_secret:
        return None
    from core.wecom_client import WeComClient

    return WeComClient(
        corp_id=settings.wecom_corp_id,
        app_secret=settings.wecom_app_secret,
        agent_id=settings.wecom_agent_id,
    )


def _get_store_plan_code(session, store_id: int) -> str:
    from services.subscriptions import ensure_store_subscription

    subscription = ensure_store_subscription(session, store_id)
    return subscription.plan.code if subscription.plan else "starter"


def register_outreach_jobs(scheduler, session_factory):
    from app.models import Store
    from outreach.auto_sender import send_auto_outreach
    from outreach.engine import dispatch_outreach

    def scan_and_dispatch():
        session = session_factory()
        try:
            for store in session.query(Store).all():
                plan_code = _get_store_plan_code(session, store.id)
                dispatch_outreach(session, store.id, plan_code=plan_code)
        finally:
            session.close()

    def auto_send_batch():
        session = session_factory()
        try:
            client = _create_wecom_client()
            for store in session.query(Store).all():
                plan_code = _get_store_plan_code(session, store.id)
                send_auto_outreach(session, client=client, plan_code=plan_code)
        finally:
            session.close()

    scheduler.add_job(scan_and_dispatch, "cron", hour=8, minute=0, id="outreach_scan")
    scheduler.add_job(auto_send_batch, "cron", hour=10, minute=0, id="outreach_send_morning")
    scheduler.add_job(auto_send_batch, "cron", hour=14, minute=0, id="outreach_send_afternoon")
    scheduler.add_job(auto_send_batch, "cron", hour=18, minute=0, id="outreach_send_evening")
