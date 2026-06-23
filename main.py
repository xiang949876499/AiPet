import click
from rich.console import Console
from rich.table import Table

from agents.content import ContentAgent
from agents.reminder import ReminderAgent
from app.config import settings
from app.database import SessionLocal, init_db
from agents.sample import SampleAgent
from app.models import Appointment, ContentItem, Customer, FollowTask, PushTask, SampleTrial, Store, SubscriptionPlan
from core.wecom_client import WeComClient
from seed_data import seed_demo_data
from services.customer_import import import_customers_from_csv
from services.push_tasks import create_internal_push_task
from services.subscriptions import seed_subscription_plans
from services.weekly_plan import build_7_day_ops_plan
from services.wecom_push import send_push_task

console = Console()


@click.group()
def cli():
    pass


@cli.command("init-db")
def init_db_command():
    init_db()
    console.print("数据库已初始化")


@cli.command("seed")
def seed_command():
    init_db()
    session = SessionLocal()
    try:
        result = seed_demo_data(session)
        console.print(f"演示数据已导入：{result['created']} 条客户记录")
    finally:
        session.close()


@cli.command("dashboard")
def dashboard_command():
    init_db()
    session = SessionLocal()
    try:
        ReminderAgent(session).execute({})
        table = Table(title="今日工作台")
        table.add_column("指标")
        table.add_column("数量")
        table.add_row("客户数", str(session.query(Customer).count()))
        table.add_row("待跟进", str(session.query(FollowTask).filter_by(status="待处理").count()))
        console.print(table)
    finally:
        session.close()


@cli.group("reminders")
def reminders_group():
    pass


@reminders_group.command("pending")
def reminders_pending_command():
    init_db()
    session = SessionLocal()
    try:
        ReminderAgent(session).execute({})
        table = Table(title="待跟进任务")
        table.add_column("客户")
        table.add_column("宠物")
        table.add_column("原因")
        table.add_column("话术")
        for task in session.query(FollowTask).filter_by(status="待处理").all():
            table.add_row(task.customer.name, task.pet.name, task.reason, task.ai_message or "")
        console.print(table)
    finally:
        session.close()


@cli.group("customers")
def customers_group():
    pass


@customers_group.command("list")
def customers_list_command():
    init_db()
    session = SessionLocal()
    try:
        table = Table(title="客户列表")
        table.add_column("客户")
        table.add_column("微信")
        table.add_column("到店次数")
        for customer in session.query(Customer).order_by(Customer.id).all():
            table.add_row(customer.name, customer.wechat_name or "", str(customer.visit_count))
        console.print(table)
    finally:
        session.close()


@customers_group.command("import-csv")
@click.option("--path", "csv_path", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--store-id", type=int)
def customers_import_csv_command(csv_path: str, store_id: int | None):
    init_db()
    session = SessionLocal()
    try:
        if store_id is None:
            store = session.query(Store).order_by(Store.id.asc()).first()
            store_id = store.id if store else None
        if store_id is None:
            console.print("没有可导入的门店，请先创建或导入演示数据")
            return
        result = import_customers_from_csv(session, store_id, csv_path)
        console.print(
            "导入客户完成："
            f"新增客户 {result['created_customers']}，"
            f"更新客户 {result['updated_customers']}，"
            f"新增宠物 {result['created_pets']}，"
            f"跳过 {result['skipped']}"
        )
    finally:
        session.close()


@cli.group("appointments")
def appointments_group():
    pass


@appointments_group.command("today")
def appointments_today_command():
    init_db()
    session = SessionLocal()
    try:
        table = Table(title="今日预约")
        table.add_column("服务")
        table.add_column("状态")
        appointments = session.query(Appointment).order_by(Appointment.start_time).all()
        for appointment in appointments:
            table.add_row(appointment.service_type, appointment.status)
        console.print(table)
    finally:
        session.close()


@cli.group("sample")
def sample_group():
    pass


@sample_group.command("pending")
def sample_pending_command():
    init_db()
    session = SessionLocal()
    try:
        SampleAgent(session).execute({})
        table = Table(title="试用装待回访")
        table.add_column("客户ID")
        table.add_column("宠物ID")
        table.add_column("状态")
        trials = session.query(SampleTrial).filter(SampleTrial.follow_time.is_not(None)).all()
        for trial in trials:
            table.add_row(str(trial.customer_id), str(trial.pet_id), trial.feedback or "待反馈")
        console.print(table)
    finally:
        session.close()


@cli.group("subscription")
def subscription_group():
    pass


@subscription_group.command("plans")
def subscription_plans_command():
    init_db()
    session = SessionLocal()
    try:
        seed_subscription_plans(session)
        table = Table(title="订阅套餐")
        table.add_column("套餐")
        table.add_column("月付")
        table.add_column("年付")
        table.add_column("AI额度")
        table.add_column("能力")
        for plan in session.query(SubscriptionPlan).order_by(SubscriptionPlan.monthly_price).all():
            name = f"{plan.name}{'（推荐）' if plan.is_recommended else ''}"
            table.add_row(name, str(plan.monthly_price), str(plan.annual_price), str(plan.ai_quota_monthly), plan.features)
        console.print(table)
    finally:
        session.close()


@cli.group("content")
def content_group():
    pass


@content_group.command("generate")
@click.option("--store-id", type=int)
def content_generate_command(store_id: int | None):
    init_db()
    session = SessionLocal()
    try:
        if store_id is None:
            store = session.query(Store).order_by(Store.id.asc()).first()
            store_id = store.id if store else None
        result = ContentAgent(session).execute({"store_id": store_id})
        console.print(f"今日内容已生成：{result['created']} 条")
    finally:
        session.close()


@content_group.command("list")
def content_list_command():
    init_db()
    session = SessionLocal()
    try:
        table = Table(title="今日内容日历")
        table.add_column("渠道")
        table.add_column("标题")
        table.add_column("正文")
        for item in session.query(ContentItem).order_by(ContentItem.created_at.desc()).all():
            table.add_row(item.channel, item.title, item.body)
        console.print(table)
    finally:
        session.close()


@cli.group("ops")
def ops_group():
    pass


@ops_group.command("plan-7-days")
@click.option("--store-id", type=int)
def ops_plan_7_days_command(store_id: int | None):
    init_db()
    session = SessionLocal()
    try:
        if store_id is None:
            store = session.query(Store).order_by(Store.id.asc()).first()
            store_id = store.id if store else None
        if store_id is None:
            console.print("没有可生成计划的门店，请先创建或导入演示数据")
            return
        table = Table(title="7 天运营计划")
        table.add_column("日期")
        table.add_column("渠道")
        table.add_column("客户重点")
        table.add_column("内容主题")
        table.add_column("建议动作")
        for item in build_7_day_ops_plan(session, store_id):
            table.add_row(
                item["date"],
                item["channel"],
                item["customer_focus"],
                item["content_topic"],
                item["suggested_action"],
            )
        console.print(table)
    finally:
        session.close()


@cli.group("push")
def push_group():
    pass


def _push_status_label(status: str) -> str:
    return {
        "pending": "待确认",
        "approved": "已确认",
        "sent": "已发送",
        "failed": "发送失败",
        "skipped": "已跳过",
        "cancelled": "已取消",
    }.get(status, status)


@push_group.command("list")
def push_list_command():
    init_db()
    session = SessionLocal()
    try:
        table = Table(title="推送任务")
        table.add_column("ID")
        table.add_column("渠道")
        table.add_column("接收人")
        table.add_column("场景")
        table.add_column("状态")
        table.add_column("内容")
        tasks = session.query(PushTask).order_by(PushTask.id).all()
        for task in tasks:
            table.add_row(
                str(task.id),
                task.channel,
                task.receiver_id,
                task.scene,
                _push_status_label(task.status),
                task.content,
            )
        console.print(table)
    finally:
        session.close()


@push_group.command("create-internal")
@click.option("--follow-task-id", type=int, required=True)
@click.option("--staff-id", type=int, required=True)
def push_create_internal_command(follow_task_id: int, staff_id: int):
    init_db()
    session = SessionLocal()
    try:
        task = create_internal_push_task(session, follow_task_id, staff_id)
        console.print(f"已创建内部推送任务：{task.id}")
    finally:
        session.close()


@push_group.command("send-internal")
@click.option("--dry-run", is_flag=True, help="Print pending pushes without calling Enterprise WeChat.")
def push_send_internal_command(dry_run: bool):
    init_db()
    session = SessionLocal()
    try:
        tasks = (
            session.query(PushTask)
            .filter(PushTask.channel == "wecom_internal", PushTask.status.in_(["pending", "approved"]))
            .order_by(PushTask.id)
            .all()
        )
        if dry_run:
            for task in tasks:
                console.print(f"dry-run push #{task.id} to {task.receiver_id}: {task.content}")
            if not tasks:
                console.print("dry-run: 没有待发送的内部推送任务")
            return

        if not settings.wecom_internal_notify_enabled:
            console.print("企业微信内部通知未启用，请设置 WECOM_INTERNAL_NOTIFY_ENABLED=true")
            return

        client = WeComClient(
            corp_id=settings.wecom_corp_id,
            app_secret=settings.wecom_app_secret,
            agent_id=settings.wecom_agent_id,
        )
        for task in tasks:
            result = send_push_task(session, task.id, client)
            console.print(f"push #{task.id}: {'sent' if result.get('sent') else 'failed'}")
    finally:
        session.close()


@cli.command("activate")
@click.option("--code", prompt="Activation code")
@click.option("--store-name", prompt="Store name")
@click.option("--phone", default="")
def activate_command(code: str, store_name: str, phone: str):
    import hashlib
    import platform
    import uuid

    from licensing.client import LicenseClient
    from licensing.storage import LicenseStorage

    machine_id = hashlib.sha256(f"{platform.node()}-{uuid.getnode()}".encode()).hexdigest()[:32]
    client = LicenseClient()
    result = client.activate(code, store_name, phone, machine_id)
    if result:
        LicenseStorage().save_token(result["token"], result["plan_code"], result["expires_at"])
        console.print(f"Activated plan {result['plan_code']} until {result['expires_at']}")
    else:
        console.print(f"Activation failed: {client.last_error}")


@cli.command("trial")
def trial_command():
    from licensing.storage import LicenseStorage

    token = LicenseStorage().create_trial_token()
    if token is None:
        console.print("[red]已存在付费 license，无法覆盖为试用。[/red]")
        return
    console.print(f"Started 14-day growth trial: {token['expires_at']}")


@cli.group("license")
def license_group():
    pass


@license_group.command("status")
def license_status_command():
    from licensing.storage import LicenseStorage

    status = LicenseStorage().get_status()
    table = Table(title="License status")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["mode", "plan_code", "expires_at", "offline_remaining_days", "remaining_ai_calls"]:
        table.add_row(key, str(status.get(key)))
    console.print(table)


@cli.group("outreach")
def outreach_group():
    pass


@outreach_group.command("scan")
def outreach_scan_command():
    init_db()
    session = SessionLocal()
    try:
        from outreach.engine import dispatch_outreach

        store = session.query(Store).order_by(Store.id.asc()).first()
        from licensing.storage import LicenseStorage
        token_data = LicenseStorage().get_token()
        plan_code = token_data.get("plan_code", "starter") if token_data else "starter"
        result = dispatch_outreach(session, store.id, plan_code=plan_code) if store else {"created": 0, "skipped": 0}
        console.print(f"Generated {result['created']} outreach tasks, skipped {result['skipped']}.")
    finally:
        session.close()


@outreach_group.command("confirm-list")
def outreach_confirm_list_command():
    init_db()
    session = SessionLocal()
    try:
        from outreach.confirm_flow import get_pending_confirmations

        store = session.query(Store).order_by(Store.id.asc()).first()
        messages = get_pending_confirmations(session, store.id) if store else []
        table = Table(title="Pending outreach confirmations")
        table.add_column("ID")
        table.add_column("Customer")
        table.add_column("Pet")
        table.add_column("Message")
        for item in messages:
            table.add_row(str(item["log_id"]), item["customer_name"], item["pet_name"], item["ai_message"][:80])
        console.print(table)
    finally:
        session.close()


@content_group.command("calendar")
@click.option("--store-id", type=int)
def content_calendar_command(store_id: int | None):
    init_db()
    session = SessionLocal()
    try:
        from content_engine.calendar import build_content_calendar

        if store_id is None:
            store = session.query(Store).order_by(Store.id.asc()).first()
            store_id = store.id if store else None
        items = build_content_calendar(session, store_id) if store_id else []
        table = Table(title="Content calendar")
        table.add_column("Date")
        table.add_column("Channel")
        table.add_column("Template")
        table.add_column("Status")
        for item in items:
            table.add_row(item["date"], item["channel"], item["template_code"], item["status"])
        console.print(table)
    finally:
        session.close()


@cli.group("analytics")
def analytics_group():
    pass


@analytics_group.command("dashboard")
def analytics_dashboard_command():
    init_db()
    session = SessionLocal()
    try:
        from analytics.dashboard import build_tiered_dashboard
        from licensing.storage import LicenseStorage

        store = session.query(Store).order_by(Store.id.asc()).first()
        token_data = LicenseStorage().get_token()
        plan_code = token_data.get("plan_code", "starter") if token_data else "starter"
        data = build_tiered_dashboard(session, store.id, plan_code) if store else {"metrics": {}}
        table = Table(title=f"Analytics dashboard ({plan_code})")
        table.add_column("Metric")
        table.add_column("Value")
        for key, value in data.get("metrics", {}).items():
            table.add_row(key, str(value))
        console.print(table)
    finally:
        session.close()


if __name__ == "__main__":
    cli()
