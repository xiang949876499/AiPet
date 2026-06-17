import click
from rich.console import Console
from rich.table import Table

from agents.reminder import ReminderAgent
from app.config import settings
from app.database import SessionLocal, init_db
from agents.sample import SampleAgent
from app.models import Appointment, Customer, FollowTask, PushTask, SampleTrial
from core.wecom_client import WeComClient
from seed_data import seed_demo_data
from services.push_tasks import create_internal_push_task
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


if __name__ == "__main__":
    cli()
