from datetime import datetime, timedelta


def _seed_customer_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'customer-detail.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from agents.reminder import ReminderAgent
    from app.database import SessionLocal, init_db
    from app.models import ServiceRecord
    from seed_data import seed_demo_data

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        customer = session.query(__import__("app.models", fromlist=["Customer"]).Customer).first()
        pet = customer.pets[0]
        session.add(
            ServiceRecord(
                store_id=customer.store_id,
                customer_id=customer.id,
                pet_id=pet.id,
                service_type="洗护",
                service_time=datetime.utcnow() - timedelta(days=45),
                amount=168,
                note="详情页测试记录",
            )
        )
        session.commit()
        ReminderAgent(session).execute({})
        return customer.id
    finally:
        session.close()


def test_customer_list_links_to_customer_detail(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer
    from fastapi.testclient import TestClient
    from web.app import create_app

    session = SessionLocal()
    try:
        customer = session.get(Customer, customer_id)
        customer.do_not_disturb = True
        session.commit()
    finally:
        session.close()

    client = TestClient(create_app())
    response = client.get("/customers")

    assert response.status_code == 200
    assert f'href="/customers/{customer_id}"' in response.text
    assert "查看档案" in response.text
    assert "<th>状态</th>" in response.text
    assert "免打扰" in response.text


def test_customer_list_filters_by_pending_dnd_and_due(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer
    from fastapi.testclient import TestClient
    from web.app import create_app

    session = SessionLocal()
    try:
        customer = session.get(Customer, customer_id)
        customer.do_not_disturb = True
        session.commit()
    finally:
        session.close()

    client = TestClient(create_app())

    pending = client.get("/customers?filter=pending")
    assert pending.status_code == 200
    assert "筛选：待跟进" in pending.text
    assert f'href="/customers/{customer_id}"' in pending.text
    assert "待跟进" in pending.text

    dnd = client.get("/customers?filter=dnd")
    assert dnd.status_code == 200
    assert "筛选：免打扰" in dnd.text
    assert f'href="/customers/{customer_id}"' in dnd.text
    assert "免打扰" in dnd.text

    due = client.get("/customers?filter=due")
    assert due.status_code == 200
    assert "筛选：最近到店超期" in due.text
    assert f'href="/customers/{customer_id}"' in due.text
    assert "已超期" in due.text


def test_customer_list_batch_marks_pending_tasks_sent(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import FollowTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/customers/batch",
        data={"action": "mark_sent", "customer_ids": [str(customer_id)], "return_filter": "pending"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/customers?filter=pending&batch_action=mark_sent&batch_count=1"

    session = SessionLocal()
    try:
        tasks = session.query(FollowTask).filter_by(customer_id=customer_id).all()
        assert tasks
        assert all(task.status == "已发送" for task in tasks)
    finally:
        session.close()

    notice = client.get(response.headers["location"])
    assert "已批量标记 1 条待跟进任务为已发送" in notice.text


def test_customer_list_batch_creates_internal_push_tasks(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import PushTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/customers/batch",
        data={"action": "push_internal", "customer_ids": [str(customer_id)], "return_filter": "pending"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/customers?filter=pending&batch_action=push_internal&batch_count=1"

    session = SessionLocal()
    try:
        push_tasks = session.query(PushTask).filter_by(receiver_id="wang").all()
        assert len(push_tasks) == 1
        assert "客户：" in push_tasks[0].content
    finally:
        session.close()

    notice = client.get(response.headers["location"])
    assert "已生成 1 条内部提醒任务" in notice.text
    assert "查看内部提醒" in notice.text


def test_customer_list_renders_select_all_batch_controls(tmp_path, monkeypatch):
    _seed_customer_detail(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/customers?filter=pending")

    assert response.status_code == 200
    assert 'id="select-all-customers"' in response.text
    assert 'data-customer-checkbox' in response.text
    assert 'id="selected-count"' in response.text
    assert "已选择 0 位客户" in response.text


def test_customer_detail_page_renders_profile_tasks_and_history(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == 200
    assert "客户档案" in response.text
    assert "客户概览" in response.text
    assert "宠物档案" in response.text
    assert "待跟进任务" in response.text
    assert "服务记录" in response.text
    assert "详情页测试记录" in response.text
    assert "复制话术" in response.text
    assert "生成内部提醒" in response.text
    assert "客户偏好" in response.text
    assert "当前状态" in response.text
    assert "可主动跟进" in response.text
    assert 'name="tags"' in response.text
    assert 'name="note"' in response.text
    assert 'name="do_not_disturb"' in response.text


def test_customer_detail_can_update_preferences(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.post(
        f"/customers/{customer_id}/profile",
        data={
            "tags": "高客单, 怕吵",
            "note": "洗护前先确认是否需要低敏香波",
            "do_not_disturb": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/customers/{customer_id}?saved=profile"

    session = SessionLocal()
    try:
        customer = session.get(Customer, customer_id)
        assert customer.tags == "高客单, 怕吵"
        assert customer.note == "洗护前先确认是否需要低敏香波"
        assert customer.do_not_disturb is True
    finally:
        session.close()

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "客户偏好已保存" in detail.text
    assert "高客单, 怕吵" in detail.text
    assert "洗护前先确认是否需要低敏香波" in detail.text
    assert "checked" in detail.text
    assert "免打扰" in detail.text


def test_do_not_disturb_customer_is_skipped_when_generating_reminders(tmp_path, monkeypatch):
    customer_id = _seed_customer_detail(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import FollowTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    client.post(
        f"/customers/{customer_id}/profile",
        data={"tags": "免打扰", "note": "家长要求先不主动联系", "do_not_disturb": "on"},
    )

    session = SessionLocal()
    try:
        session.query(FollowTask).delete()
        session.commit()
    finally:
        session.close()

    response = client.post("/customers/import/generate-reminders", follow_redirects=False)

    assert response.status_code == 303
    session = SessionLocal()
    try:
        assert session.query(FollowTask).filter_by(customer_id=customer_id).count() == 0
    finally:
        session.close()


def test_customer_detail_returns_404_for_missing_customer(tmp_path, monkeypatch):
    _seed_customer_detail(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/customers/999999")

    assert response.status_code == 404
