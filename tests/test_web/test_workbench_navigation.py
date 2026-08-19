def _seed_workbench(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'workbench.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()


def test_dashboard_exposes_core_workbench_navigation(tmp_path, monkeypatch):
    _seed_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    import web.app as web_app

    # "/" 在存在 Vue 构建时返回 SPA 外壳；导航断言针对 Jinja 回退模板
    monkeypatch.setattr(web_app, "_frontend_build_available", lambda: False)

    client = TestClient(web_app.create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "AI 运营工作台" in response.text
    assert "后台导航" in response.text
    assert 'href="/outreach"' in response.text
    assert 'href="/content/calendar"' in response.text
    assert "待跟进" in response.text
    assert "内容发布" in response.text
    assert "今日流程" in response.text
    assert "处理提醒" in response.text
    assert "查看推送" in response.text
    assert "生成内容" in response.text


def test_dashboard_uses_data_first_homepage_design(tmp_path, monkeypatch):
    _seed_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    import web.app as web_app

    # "/" 在存在 Vue 构建时返回 SPA 外壳；首页文案断言针对 Jinja 回退模板
    monkeypatch.setattr(web_app, "_frontend_build_available", lambda: False)

    client = TestClient(web_app.create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "PetCRM AI" in response.text
    assert "数据首页" in response.text
    assert "首页只看经营数据" in response.text
    assert "今日关键数据" in response.text
    assert "今日经营漏斗" in response.text
    assert "近 7 天趋势" in response.text
    assert "关键预警" in response.text
    assert "AI 数据摘要" in response.text
    assert "功能入口已移出首页" in response.text
    assert "data-shell" in response.text


def test_operation_pages_share_navigation_bar(tmp_path, monkeypatch):
    _seed_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    for path in ["/reminders", "/push-tasks", "/outreach", "/content/calendar", "/customers", "/appointments"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "后台导航" in response.text
        assert 'href="/"' in response.text
        assert 'href="/outreach"' in response.text
        assert 'href="/content/calendar"' in response.text


def test_support_pages_use_chinese_workbench_shell(tmp_path, monkeypatch):
    _seed_workbench(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    pages = {
        "/samples": "试用装管理",
        "/settings": "门店设置",
        "/settings/rules": "触达规则",
        "/license": "授权信息",
        "/admin/monitoring": "系统监控",
        "/outreach/confirm": "触达确认",
    }
    for path, title in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        assert "后台导航" in response.text
        assert title in response.text
        assert "Confirm" not in response.text
        assert "Reject" not in response.text
