from click.testing import CliRunner


def test_cli_seed_dashboard_and_pending_reminders(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")

    from main import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init-db"]).exit_code == 0
    seed_result = runner.invoke(cli, ["seed"])
    assert seed_result.exit_code == 0
    assert "演示数据已导入" in seed_result.output

    dashboard_result = runner.invoke(cli, ["dashboard"])
    assert dashboard_result.exit_code == 0
    assert "今日工作台" in dashboard_result.output
    assert "待跟进" in dashboard_result.output

    reminders_result = runner.invoke(cli, ["reminders", "pending"])
    assert reminders_result.exit_code == 0
    assert "待跟进任务" in reminders_result.output
    assert "洗护距今" in reminders_result.output

    customers_result = runner.invoke(cli, ["customers", "list"])
    assert customers_result.exit_code == 0
    assert "客户列表" in customers_result.output
    assert "张姐" in customers_result.output

    appointments_result = runner.invoke(cli, ["appointments", "today"])
    assert appointments_result.exit_code == 0
    assert "今日预约" in appointments_result.output

    samples_result = runner.invoke(cli, ["sample", "pending"])
    assert samples_result.exit_code == 0
    assert "试用装待回访" in samples_result.output


def test_cli_lists_and_dry_runs_internal_push_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'push.db'}")

    from app.database import SessionLocal
    from app.models import PushTask, Store
    from main import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init-db"]).exit_code == 0

    session = SessionLocal()
    try:
        store = Store(name="豆豆宠物店")
        session.add(store)
        session.flush()
        session.add(
            PushTask(
                store_id=store.id,
                channel="wecom_internal",
                receiver_type="staff",
                receiver_id="wang",
                scene="repurchase_reminder",
                content="请跟进豆豆的洗护提醒",
            )
        )
        session.commit()
    finally:
        session.close()

    list_result = runner.invoke(cli, ["push", "list"])
    assert list_result.exit_code == 0
    assert "推送任务" in list_result.output
    assert "wecom_internal" in list_result.output

    send_result = runner.invoke(cli, ["push", "send-internal", "--dry-run"])
    assert send_result.exit_code == 0
    assert "dry-run" in send_result.output
    assert "请跟进豆豆的洗护提醒" in send_result.output


def test_cli_creates_internal_push_task_from_seeded_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'push_create.db'}")

    from main import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init-db"]).exit_code == 0
    assert runner.invoke(cli, ["seed"]).exit_code == 0
    assert runner.invoke(cli, ["dashboard"]).exit_code == 0

    create_result = runner.invoke(
        cli,
        ["push", "create-internal", "--follow-task-id", "1", "--staff-id", "1"],
    )

    assert create_result.exit_code == 0
    assert "已创建内部推送任务" in create_result.output


def test_cli_lists_subscription_plans_and_generates_content(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ops.db'}")

    from main import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init-db"]).exit_code == 0
    assert runner.invoke(cli, ["seed"]).exit_code == 0

    plans_result = runner.invoke(cli, ["subscription", "plans"])
    assert plans_result.exit_code == 0
    assert "专业版" in plans_result.output
    assert "499" in plans_result.output

    content_result = runner.invoke(cli, ["content", "generate"])
    assert content_result.exit_code == 0
    assert "今日内容已生成" in content_result.output

    list_result = runner.invoke(cli, ["content", "list"])
    assert list_result.exit_code == 0
    assert "今日内容日历" in list_result.output
    assert "朋友圈" in list_result.output
