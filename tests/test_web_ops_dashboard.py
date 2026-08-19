def test_ops_dashboard_renders_subscription_content_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ops_dashboard.db'}")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data
    import web.app as web_app
    from fastapi.testclient import TestClient

    # "/" 在存在 Vue 构建时返回 SPA 外壳；此处验证 Jinja 回退工作台
    monkeypatch.setattr(web_app, "_frontend_build_available", lambda: False)

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()

    client = TestClient(web_app.create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "AI 运营工作台" in response.text
    assert "专业版" in response.text
    assert "今日客户机会" in response.text
    assert "今日内容日历" in response.text
    assert "7 天运营计划" in response.text
    assert "试用剩余" in response.text
    assert "预计挽回营业额" in response.text
