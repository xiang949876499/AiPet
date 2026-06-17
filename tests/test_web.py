def test_web_dashboard_renders_seeded_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'web.db'}")

    from app.database import init_db, SessionLocal
    from seed_data import seed_demo_data
    from web.app import create_app
    from fastapi.testclient import TestClient

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "今日工作台" in response.text
    assert "待跟进" in response.text
    assert "宠物店 AI 复购提醒助手" in response.text
