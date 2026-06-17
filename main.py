import click
from rich.console import Console
from rich.table import Table

from agents.reminder import ReminderAgent
from app.database import SessionLocal, init_db
from agents.sample import SampleAgent
from app.models import Appointment, Customer, FollowTask, SampleTrial
from seed_data import seed_demo_data

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


if __name__ == "__main__":
    cli()
