def _seed_import_store(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'customer-import.db'}")
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


def test_customer_import_page_renders_upload_guidance(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/customers/import")

    assert response.status_code == 200
    assert "导入客户数据" in response.text
    assert "上传 CSV 文件" in response.text
    assert "客户姓名,手机号,微信名,宠物名" in response.text
    assert 'href="/customers/import/template"' in response.text
    assert 'formaction="/customers/import/preview"' in response.text
    assert 'enctype="multipart/form-data"' in response.text
    assert "后台导航" in response.text


def test_customer_import_template_downloads_csv(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/customers/import/template")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=customers-template.csv" in response.headers["content-disposition"]
    assert "客户姓名,手机号,微信名,宠物名,宠物类型,品种,到店日期,服务项目,消费金额,备注" in response.text
    assert "张女士,13800000000" in response.text


def test_customer_import_preview_reports_issues_without_importing(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    csv_content = (
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "刘女士,13300000000,花花妈妈,花花,猫,橘猫,abc,2026-06-01\n"
        ",13200000000,空名客户,豆豆,狗,柯基,21,2026-06-02\n"
        "周老板,13100000000,元宝爸爸,元宝,狗,金毛,30,2026/99/99\n"
    ).encode("utf-8-sig")

    response = client.post(
        "/customers/import/preview",
        files={"csv_file": ("customers.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert "预检完成" in response.text
    assert "总行数 3" in response.text
    assert "可导入 2" in response.text
    assert "跳过 1" in response.text
    assert "第 3 行" in response.text
    assert "缺少客户姓名" in response.text
    assert "日期格式不正确" in response.text

    session = SessionLocal()
    try:
        assert session.query(Customer).filter_by(phone="13300000000").count() == 0
    finally:
        session.close()


def test_customer_import_upload_creates_customers_and_pets(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer, Pet
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    csv_content = (
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "赵老板,13500000000,团团家长,团团,狗,比熊,28,2026-06-01\n"
    ).encode("utf-8-sig")

    response = client.post(
        "/customers/import",
        files={"csv_file": ("customers.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert "导入完成" in response.text
    assert "新增客户 1" in response.text
    assert "新增宠物 1" in response.text
    assert "生成今日提醒" in response.text
    assert 'action="/customers/import/generate-reminders"' in response.text

    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(phone="13500000000").one()
        assert customer.wechat_name == "团团家长"
        pet = session.query(Pet).filter_by(customer_id=customer.id, name="团团").one()
        assert pet.care_cycle_days == 28
    finally:
        session.close()


def test_customer_import_can_generate_reminders_after_upload(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import FollowTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    csv_content = (
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "钱女士,13400000000,毛毛妈妈,毛毛,猫,布偶,21,2020-05-01\n"
    ).encode("utf-8-sig")
    client.post(
        "/customers/import",
        files={"csv_file": ("customers.csv", csv_content, "text/csv")},
    )

    response = client.post("/customers/import/generate-reminders", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/outreach?generated=1"

    reminders_page = client.get(response.headers["location"])
    assert reminders_page.status_code == 200
    assert "客户触达" in reminders_page.text
    assert "钱女士" in reminders_page.text

    session = SessionLocal()
    try:
        assert (
            session.query(FollowTask)
            .join(FollowTask.customer)
            .filter_by(phone="13400000000")
            .count()
            >= 1
        )
    finally:
        session.close()


def test_customer_import_preview_json_api_reports_summary(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    csv_content = (
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,到店日期,服务项目,消费金额,备注\n"
        "赵老板,13500000000,团团家长,团团,狗,比熊,2026-06-01,洗护,168,\n"
    ).encode("utf-8-sig")

    response = client.post(
        "/api/customers/import/preview",
        files={"csv_file": ("customers.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_rows"] == 1
    assert payload["ready_rows"] == 1
    assert payload["estimated_service_records"] == 1
    assert payload["estimated_total_amount"] == 168


def test_customer_import_json_api_creates_service_records(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer, ServiceRecord
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    csv_content = (
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,到店日期,服务项目,消费金额,备注\n"
        "孙女士,13600000000,可乐妈妈,可乐,狗,柯基,2026-06-02,商品,88,狗粮\n"
    ).encode("utf-8-sig")

    response = client.post(
        "/api/customers/import",
        files={"csv_file": ("customers.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_customers"] == 1
    assert payload["created_service_records"] == 1

    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(phone="13600000000").one()
        record = session.query(ServiceRecord).filter_by(customer_id=customer.id).one()
        assert record.service_type == "商品"
        assert float(record.amount) == 88
    finally:
        session.close()


def test_customer_outreach_queue_api_returns_items(tmp_path, monkeypatch):
    _seed_import_store(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/api/customers/outreach-queue")

    assert response.status_code == 200
    payload = response.json()
    assert {"items", "counts"} <= payload.keys()
    assert payload["counts"]["total"] == len(payload["items"])
    assert payload["items"]
    assert {"id", "customer_id", "pet_id", "ai_message", "status"} <= payload["items"][0].keys()
