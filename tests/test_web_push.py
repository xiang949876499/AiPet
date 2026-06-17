def test_push_tasks_page_renders_pending_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'web_push.db'}")

    from app.database import SessionLocal, init_db
    from app.models import PushTask
    from fastapi.testclient import TestClient
    from seed_data import seed_demo_data
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        store_id = session.query(PushTask).count() + 1
        push_task = PushTask(
            store_id=store_id,
            channel="wecom_internal",
            receiver_type="staff",
            receiver_id="wang",
            scene="repurchase_reminder",
            content="请跟进豆豆的洗护提醒",
        )
        session.add(push_task)
        session.commit()
    finally:
        session.close()

    client = TestClient(create_app())
    response = client.get("/push-tasks")

    assert response.status_code == 200
    assert "推送任务" in response.text
    assert "待确认" in response.text
    assert "请跟进豆豆的洗护提醒" in response.text
