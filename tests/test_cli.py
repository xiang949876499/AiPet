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
