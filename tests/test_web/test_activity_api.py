def _seed_activity_store(tmp_path, monkeypatch, db_name: str = "activity_api.db"):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / db_name}")
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


def _client_with_fake_llm(monkeypatch):
    from fastapi.testclient import TestClient
    import web.app as web_app

    class FakeLLMClient:
        def generate(self, prompt: str):
            return '{"title": "AI 生成标题", "body": "AI 生成正文", "image_prompt": ""}'

    monkeypatch.setattr(web_app, "LLMClient", FakeLLMClient)
    return TestClient(web_app.create_app()), web_app


def test_activity_generate_returns_copy_for_each_platform_direction(tmp_path, monkeypatch):
    _seed_activity_store(tmp_path, monkeypatch)
    client, web_app = _client_with_fake_llm(monkeypatch)

    for platform, directions in web_app.ACTIVITY_PLATFORMS.items():
        for direction in directions:
            response = client.post(
                "/api/activity/generate",
                json={"platform": platform, "direction": direction["name"], "context": "柯基洗护"},
            )

            assert response.status_code == 200
            payload = response.json()
            assert set(payload) == {"title", "body", "channel"}
            assert payload["title"] == "AI 生成标题"
            assert payload["body"] == "AI 生成正文"
            assert payload["channel"]


def test_activity_publish_writes_published_content_item(tmp_path, monkeypatch):
    _seed_activity_store(tmp_path, monkeypatch)
    client, _ = _client_with_fake_llm(monkeypatch)

    response = client.post(
        "/api/activity/publish",
        json={
            "title": "豆豆洗护焕新",
            "body": "今天的豆豆清爽又精神。",
            "channel": "moments",
            "direction": "改造前后",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "已发布"

    from app.database import SessionLocal
    from app.models import ContentItem

    session = SessionLocal()
    try:
        item = session.get(ContentItem, payload["id"])
        assert item.title == "豆豆洗护焕新"
        assert item.body == "今天的豆豆清爽又精神。"
        assert item.channel == "moments"
        assert item.topic == "改造前后"
        assert item.status == "已发布"
        assert item.published_at is not None
    finally:
        session.close()


def test_activity_generate_then_publish_flow(tmp_path, monkeypatch):
    _seed_activity_store(tmp_path, monkeypatch)
    client, _ = _client_with_fake_llm(monkeypatch)

    generated = client.post(
        "/api/activity/generate",
        json={"platform": "小红书", "direction": "品种护理", "context": "夏季护理"},
    )
    assert generated.status_code == 200

    copy = generated.json()
    published = client.post(
        "/api/activity/publish",
        json={
            "title": copy["title"],
            "body": copy["body"],
            "channel": copy["channel"],
            "direction": "品种护理",
        },
    )

    assert published.status_code == 200
    assert published.json()["status"] == "已发布"


def test_activity_generate_image_consumes_image_credit(tmp_path, monkeypatch):
    _seed_activity_store(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    import web.app as web_app
    from fastapi.testclient import TestClient
    from app.database import SessionLocal
    from app.models import Store
    from services.subscriptions import ensure_store_subscription

    monkeypatch.setattr(
        web_app,
        "_generate_activity_ai_image",
        lambda title, body: {"url": "https://example.com/activity.png", "format": "png"},
    )

    session = SessionLocal()
    try:
        store = session.query(Store).first()
        subscription = ensure_store_subscription(session, store.id, "starter")
        used_before = subscription.ai_quota_used
    finally:
        session.close()

    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/activity/generate-image",
        json={"title": "豆豆洗护焕新", "body": "今天适合发一张暖色海报。", "mode": "ai_image"},
    )

    assert response.status_code == 200
    assert response.json() == {"url": "https://example.com/activity.png", "format": "png"}

    session = SessionLocal()
    try:
        store = session.query(Store).first()
        subscription = ensure_store_subscription(session, store.id, "starter")
        assert subscription.ai_quota_used == used_before + 3
    finally:
        session.close()
