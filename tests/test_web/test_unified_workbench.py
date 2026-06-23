from datetime import datetime, timedelta


def _seed_unified_workbench(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'unified_workbench.db'}")

    from agents.reminder import ReminderAgent
    from app.database import SessionLocal, init_db
    from app.models import Staff
    from seed_data import seed_demo_data
    from services.push_tasks import create_internal_push_task

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        ReminderAgent(session).execute({})
        task = session.query(__import__("app.models", fromlist=["FollowTask"]).FollowTask).first()
        staff = Staff(store_id=task.store_id, name="店员小林", role="staff", wecom_userid="lin")
        session.add(staff)
        session.flush()
        create_internal_push_task(session, task.id, staff.id)
        task.due_date = datetime.utcnow() + timedelta(hours=4)
        session.commit()
    finally:
        session.close()


def test_unified_outreach_page_collects_touch_workflow(tmp_path, monkeypatch):
    _seed_unified_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    response = client.get("/outreach")

    assert response.status_code == 200
    assert "客户触达" in response.text
    assert "待生成话术" in response.text
    assert "待确认" in response.text
    assert "待发送" in response.text
    assert "决策依据" in response.text


def test_workbench_navigation_points_to_unified_outreach(tmp_path, monkeypatch):
    _seed_unified_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/outreach"' in response.text
    assert "客户触达" in response.text
    assert "/reminders" not in response.text
    assert "/push-tasks" not in response.text


def test_global_shell_exposes_secondary_workflow_shortcuts(tmp_path, monkeypatch):
    _seed_unified_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    for href, label in [
        ('href="/customers/import"', "导入客户"),
        ('href="/activity"', "活动方案"),
        ('href="/audit"', "门店体检"),
        ('href="/advisor"', "AI 顾问"),
        ('href="/license"', "授权额度"),
    ]:
        assert href in response.text
        assert label in response.text


def test_static_shell_assets_are_served(tmp_path, monkeypatch):
    _seed_unified_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    response = client.get("/static/app.css")

    assert response.status_code == 200
    assert "--color-primary" in response.text
    assert ".app-shell" in response.text

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "data-shell-menu" in script.text
    assert "aria-expanded" in script.text
    assert "Escape" in script.text
