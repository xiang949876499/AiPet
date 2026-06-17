from datetime import datetime


class FakeWeComClient:
    def __init__(self, result):
        self.result = result
        self.sent = []

    def send_internal_text(self, to_user: str, content: str):
        self.sent.append((to_user, content))
        return self.result


def create_push_task(db_session, sample_records, **overrides):
    from app.models import PushTask

    values = {
        "store_id": sample_records["store"].id,
        "follow_task_id": None,
        "channel": "wecom_internal",
        "receiver_type": "staff",
        "receiver_id": "wang",
        "scene": "repurchase_reminder",
        "content": "请跟进豆豆的洗护提醒",
    }
    values.update(overrides)
    push_task = PushTask(**values)
    db_session.add(push_task)
    db_session.commit()
    return push_task


def test_send_internal_push_task_marks_sent(db_session, sample_records):
    from services.wecom_push import send_push_task

    push_task = create_push_task(db_session, sample_records)
    fake_client = FakeWeComClient(result={"errcode": 0, "errmsg": "ok"})

    result = send_push_task(db_session, push_task.id, fake_client)

    assert result["sent"] is True
    assert fake_client.sent == [("wang", "请跟进豆豆的洗护提醒")]
    assert push_task.status == "sent"
    assert isinstance(push_task.sent_at, datetime)


def test_send_internal_push_task_records_failure(db_session, sample_records):
    from services.wecom_push import send_push_task

    push_task = create_push_task(db_session, sample_records)
    fake_client = FakeWeComClient(result={"errcode": 40014, "errmsg": "invalid access_token"})

    result = send_push_task(db_session, push_task.id, fake_client)

    assert result["sent"] is False
    assert push_task.status == "failed"
    assert "invalid access_token" in push_task.error_message
