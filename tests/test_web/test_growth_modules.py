def _seed_store(tmp_path, monkeypatch, db_name: str):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / db_name}")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()


def test_store_audit_page_generates_manual_report(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, "audit.db")

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    page = client.get("/audit")
    assert page.status_code == 200
    assert "门店营销体检报告" in page.text

    response = client.post(
        "/audit",
        data={
            "store_name": "豆豆宠物生活馆",
            "city": "上海",
            "district": "社区商圈",
            "services": "洗护, 零售",
            "avg_order_value": "128",
        },
    )

    assert response.status_code == 200
    assert "定位诊断" in response.text
    assert "复购诊断" in response.text
    assert "7 天行动清单" in response.text
    assert "医疗诊断" not in response.text


def test_activity_generator_outputs_marketing_copy(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, "activity.db")

    from fastapi.testclient import TestClient
    import web.app as web_app

    class FakeLLMClient:
        def generate(self, prompt: str):
            return '{"title": "豆豆焕新日记", "body": "今天适合发布一条温暖的洗护前后对比。", "image_prompt": ""}'

    monkeypatch.setattr(web_app, "LLMClient", FakeLLMClient)

    client = TestClient(web_app.create_app())

    page = client.get("/activity")
    assert page.status_code == 200
    assert "营销文案生成器" in page.text

    response = client.post(
        "/api/activity/generate",
        json={"platform": "抖音", "direction": "改造前后", "context": "基础洗护 9 折"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "豆豆焕新日记",
        "body": "今天适合发布一条温暖的洗护前后对比。",
        "channel": "douyin",
    }


def test_weekly_report_reads_operating_data(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, "weekly.db")

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    response = client.get("/weekly-report")

    assert response.status_code == 200
    assert "每周复盘报告" in response.text
    assert "触达数" in response.text
    assert "预计挽回收入" in response.text
    assert "下周建议" in response.text


def test_advisor_page_answers_business_questions_and_blocks_medical(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, "advisor.db")

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    page = client.get("/advisor")
    assert page.status_code == 200
    assert "AI 经营顾问" in page.text

    response = client.post("/advisor", data={"question": "狗狗皮肤病怎么用药？"})

    assert response.status_code == 200
    assert "专业兽医" in response.text
    assert "日常护理参考" in response.text
