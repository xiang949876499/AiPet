import click
from rich.console import Console
from rich.table import Table

from agents.reminder import ReminderAgent
from app.database import SessionLocal, init_db
from app.models import Customer, FollowTask
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


if __name__ == "__main__":
    cli()
