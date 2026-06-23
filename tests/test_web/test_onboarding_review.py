def test_onboarding_page_guides_first_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'onboarding.db'}")

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    response = client.get("/onboarding")

    assert response.status_code == 200
    assert "3 分钟完成首次设置" in response.text
    assert "导入客户数据" in response.text
    assert 'href="/customers/import"' in response.text


def test_review_assist_page_and_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'review.db'}")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data
    from fastapi.testclient import TestClient
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()

    client = TestClient(create_app())

    page = client.get("/review")
    assert page.status_code == 200
    assert "点评助手" in page.text

    response = client.post(
        "/review",
        data={"scenario": "negative", "review_text": "服务不错，但等太久了"},
    )

    assert response.status_code == 200
    assert "推荐回复" in response.text
    assert "抱歉" in response.text
