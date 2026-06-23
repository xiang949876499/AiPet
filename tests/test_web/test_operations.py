import json
from datetime import datetime


def _seed_ops_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'operations.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from agents.reminder import ReminderAgent
    from app.database import SessionLocal, init_db
    from app.models import ContentItem, PushTask
    from seed_data import seed_demo_data

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        ReminderAgent(session).execute({})
        store = session.query(__import__("app.models", fromlist=["Store"]).Store).first()
        staff = session.query(__import__("app.models", fromlist=["Staff"]).Staff).first()
        follow_task = session.query(__import__("app.models", fromlist=["FollowTask"]).FollowTask).first()
        content = ContentItem(
            store_id=store.id,
            channel="小红书",
            topic="洗护前后对比",
            title="豆豆洗护日记",
            body="今天的豆豆蓬松又精神。",
            hashtags="#宠物洗护",
            status="draft",
        )
        push_task = PushTask(
            store_id=store.id,
            follow_task_id=follow_task.id,
            channel="wecom_internal",
            receiver_type="staff",
            receiver_id=staff.wecom_userid,
            scene="repurchase_reminder",
            content="请跟进豆豆的洗护提醒",
        )
        session.add_all([content, push_task])
        session.commit()
        return {
            "follow_task_id": follow_task.id,
            "push_task_id": push_task.id,
            "content_id": content.id,
        }
    finally:
        session.close()


def test_reminder_actions_mark_sent_and_create_internal_push(tmp_path, monkeypatch):
    ids = _seed_ops_data(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import FollowTask, PushTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    push_response = client.post(f"/reminders/{ids['follow_task_id']}/push-internal", follow_redirects=False)
    assert push_response.status_code == 303
    assert push_response.headers["location"] == "/outreach#send"

    sent_response = client.post(f"/reminders/{ids['follow_task_id']}/mark-sent", follow_redirects=False)
    assert sent_response.status_code == 303
    assert sent_response.headers["location"] == "/outreach"

    session = SessionLocal()
    try:
        task = session.get(FollowTask, ids["follow_task_id"])
        assert task.status == "已发送"
        assert session.query(PushTask).filter_by(follow_task_id=ids["follow_task_id"]).count() >= 2
    finally:
        session.close()


def test_push_task_actions_approve_skip_and_send_with_fake_client(tmp_path, monkeypatch):
    ids = _seed_ops_data(tmp_path, monkeypatch)
    monkeypatch.setenv("WECOM_INTERNAL_NOTIFY_ENABLED", "true")

    from app.database import SessionLocal
    from app.models import PushTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    class FakeWeComClient:
        corp_id = "corp"

        def send_internal_text(self, to_user: str, content: str):
            return {"errcode": 0, "errmsg": "ok"}

    client = TestClient(create_app(wecom_client_factory=lambda: FakeWeComClient()))

    approve = client.post(f"/push-tasks/{ids['push_task_id']}/approve", follow_redirects=False)
    assert approve.status_code == 303
    assert approve.headers["location"] == "/outreach#send"
    send = client.post(f"/push-tasks/{ids['push_task_id']}/send", follow_redirects=False)
    assert send.status_code == 303
    assert send.headers["location"] == "/outreach#send"

    session = SessionLocal()
    try:
        task = session.get(PushTask, ids["push_task_id"])
        assert task.status == "sent"
        assert task.sent_at is not None
    finally:
        session.close()

    second = _seed_ops_data(tmp_path, monkeypatch)
    skip = client.post(f"/push-tasks/{second['push_task_id']}/skip", follow_redirects=False)
    assert skip.status_code == 303
    assert skip.headers["location"] == "/outreach#send"


def test_content_actions_generate_and_publish_with_interactions(tmp_path, monkeypatch):
    ids = _seed_ops_data(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import ContentItem
    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    generate = client.post("/content/generate", follow_redirects=False)
    assert generate.status_code == 303

    publish = client.post(
        f"/content/{ids['content_id']}/publish",
        data={"likes": "8", "comments": "2", "shares": "1", "consultations": "3"},
        follow_redirects=False,
    )
    assert publish.status_code == 303

    session = SessionLocal()
    try:
        item = session.get(ContentItem, ids["content_id"])
        assert item.status == "published"
        assert item.published_at is not None
        assert json.loads(item.interaction_data)["consultations"] == 3
    finally:
        session.close()


def test_operation_pages_render_action_controls(tmp_path, monkeypatch):
    _seed_ops_data(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())

    reminders = client.get("/outreach")
    push_tasks = client.get("/outreach")
    content = client.get("/content/calendar")

    assert "标记已发送" in reminders.text
    assert "生成内部提醒" in reminders.text
    assert "确认发送" in push_tasks.text
    assert "跳过" in push_tasks.text
    assert "标记已发布" in content.text
    assert "生成今日内容" in content.text
