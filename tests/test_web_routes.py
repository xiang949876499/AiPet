from datetime import datetime, timedelta


def _seed_web_route_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'web_routes.db'}")

    from app.database import SessionLocal, init_db
    from app.models import Appointment, Product, SampleTrial
    from agents.reminder import ReminderAgent
    from seed_data import seed_demo_data

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        ReminderAgent(session).execute({})
        customer = session.query(__import__("app.models", fromlist=["Customer"]).Customer).first()
        pet = customer.pets[0]
        product = Product(store_id=customer.store_id, name="冻干试吃装", category="零食")
        session.add(product)
        session.flush()
        session.add(
            Appointment(
                store_id=customer.store_id,
                customer_id=customer.id,
                pet_id=pet.id,
                service_type="洗护",
                start_time=datetime.utcnow() + timedelta(hours=2),
                end_time=datetime.utcnow() + timedelta(hours=3),
                status="已确认",
            )
        )
        session.add(
            SampleTrial(
                store_id=customer.store_id,
                customer_id=customer.id,
                pet_id=pet.id,
                product_id=product.id,
                receive_time=datetime.utcnow() - timedelta(days=1),
                feedback="待反馈",
            )
        )
        session.commit()
    finally:
        session.close()


def test_api_routes_expose_core_workbench_data(tmp_path, monkeypatch):
    _seed_web_route_data(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    customers = client.get("/api/customers")
    appointments = client.get("/api/appointments")
    reminders = client.get("/api/reminders?status=pending")
    samples = client.get("/api/samples")

    assert customers.status_code == 200
    assert customers.json()[0]["pet_names"]
    assert appointments.status_code == 200
    assert appointments.json()[0]["service_type"] == "洗护"
    assert reminders.status_code == 200
    assert reminders.json()[0]["status"] == "待处理"
    assert samples.status_code == 200
    assert samples.json()[0]["product_name"] == "冻干试吃装"


def test_api_can_mark_reminder_sent(tmp_path, monkeypatch):
    _seed_web_route_data(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    task = client.get("/api/reminders?status=pending").json()[0]

    response = client.post(f"/api/reminders/{task['id']}/send")

    assert response.status_code == 200
    assert response.json()["status"] == "已发送"
    pending_ids = [item["id"] for item in client.get("/api/reminders?status=pending").json()]
    assert task["id"] not in pending_ids


def test_web_pages_render_core_sections(tmp_path, monkeypatch):
    _seed_web_route_data(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    pages = {
        "/customers": "客户管理",
        "/appointments": "预约管理",
        "/reminders": "客户触达",
        "/samples": "试用装管理",
    }
    for path, title in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        assert title in response.text
