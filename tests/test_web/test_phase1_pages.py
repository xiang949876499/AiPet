def test_phase1_management_pages_render(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase1_web.db'}")

    from fastapi.testclient import TestClient

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()

    client = TestClient(create_app())

    for path, expected in [
        ("/license", "授权信息"),
        ("/settings", "门店设置"),
        ("/settings/rules", "触达规则"),
        ("/admin/monitoring", "系统监控"),
        ("/content/calendar", "内容日历"),
        ("/outreach/confirm", "触达确认"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.text
        assert "后台导航" in response.text
