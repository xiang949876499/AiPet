def _seed_credit_web(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'credit_web.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data
    from services.subscriptions import ensure_store_subscription

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        store = session.query(__import__("app.models", fromlist=["Store"]).Store).first()
        ensure_store_subscription(session, store.id, "starter")
    finally:
        session.close()


def test_credit_usage_is_visible_on_dashboard_and_license_page(tmp_path, monkeypatch):
    _seed_credit_web(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    import web.app as web_app

    # 本地存在 Vue 构建时 "/" 返回 SPA 外壳；Credit 用量在 Jinja 回退模板与 /license 中验证
    monkeypatch.setattr(web_app, "_frontend_build_available", lambda: False)

    client = TestClient(web_app.create_app())

    dashboard = client.get("/")
    license_page = client.get("/license")

    assert dashboard.status_code == 200
    assert "本月已用" in dashboard.text
    assert "Credit" in dashboard.text
    assert "剩余 AI 额度" not in dashboard.text

    assert license_page.status_code == 200
    assert "本月已用" in license_page.text
    assert "剩余 AI 调用" not in license_page.text


def test_growth_actions_consume_credit(tmp_path, monkeypatch):
    _seed_credit_web(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import StoreSubscription
    from fastapi.testclient import TestClient
    import web.app as web_app

    class FakeLLMClient:
        def generate(self, prompt: str):
            return '{"title": "老客洗护提醒", "body": "适合发布一条轻量营销文案。", "image_prompt": ""}'

    monkeypatch.setattr(web_app, "LLMClient", FakeLLMClient)

    client = TestClient(web_app.create_app())

    session = SessionLocal()
    try:
        before_used = session.query(StoreSubscription).one().ai_quota_used
    finally:
        session.close()

    assert client.post("/review", data={"scenario": "positive", "review_text": "洗得很干净"}).status_code == 200
    assert client.post(
        "/api/activity/generate",
        json={"platform": "抖音", "direction": "改造前后", "context": "45 天未到店，9 折"},
    ).status_code == 200
    assert client.post(
        "/audit",
        data={"store_name": "豆豆宠物", "city": "上海", "district": "社区", "services": "洗护"},
    ).status_code == 200
    assert client.get("/weekly-report").status_code == 200
    assert client.post("/advisor", data={"question": "客户嫌贵怎么回？"}).status_code == 200

    session = SessionLocal()
    try:
        subscription = session.query(StoreSubscription).one()
        assert subscription.ai_quota_used - before_used == 47
    finally:
        session.close()


def test_legacy_pages_use_unified_shell_and_static_css(tmp_path, monkeypatch):
    _seed_credit_web(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    pages = [
        "/customers",
        "/customers/import",
        "/appointments",
        "/samples",
        "/content/calendar",
        "/license",
        "/settings",
        "/settings/rules",
        "/admin/monitoring",
        "/outreach/confirm",
    ]
    for path in pages:
        response = client.get(path)
        assert response.status_code == 200
        assert '<link rel="stylesheet" href="/static/app.css">' in response.text
        assert '<script src="/static/app.js" defer></script>' in response.text
        assert '<div class="app-shell">' in response.text
        assert 'aria-expanded="false"' in response.text
        assert 'name="global_search"' in response.text
        assert "待处理" in response.text
        assert "当前角色" in response.text
        assert "快捷入口" in response.text
        assert "<!doctype html>" in response.text
