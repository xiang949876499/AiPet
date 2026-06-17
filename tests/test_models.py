from datetime import datetime, timedelta


def test_customer_pet_service_record_relationships(db_session):
    from app.models import Customer, Pet, ServiceRecord, Store

    store = Store(name="宠物店", owner_name="老板", phone="13800000000", business_type="综合店")
    db_session.add(store)
    db_session.flush()

    customer = Customer(store_id=store.id, name="李先生", phone="13900000000", visit_count=1)
    db_session.add(customer)
    db_session.flush()

    pet = Pet(store_id=store.id, customer_id=customer.id, name="奶茶", pet_type="猫", care_cycle_days=30)
    db_session.add(pet)
    db_session.flush()

    service = ServiceRecord(
        store_id=store.id,
        customer_id=customer.id,
        pet_id=pet.id,
        service_type="洗护",
        service_time=datetime.utcnow() - timedelta(days=31),
        amount=168,
    )
    db_session.add(service)
    db_session.commit()

    saved = db_session.query(Customer).filter_by(name="李先生").one()
    assert saved.pets[0].name == "奶茶"
    assert saved.service_records[0].service_type == "洗护"


def test_follow_task_records_ai_message_and_result(db_session, sample_records):
    from app.models import FollowTask

    task = FollowTask(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        task_type="洗护提醒",
        priority="高",
        reason="豆豆上次洗护距今 24 天",
        suggested_action="发送温和预约提醒",
        ai_message="张姐，豆豆上次洗护快 3 周啦。",
        result="已预约",
    )
    db_session.add(task)
    db_session.commit()

    saved = db_session.query(FollowTask).one()
    assert saved.customer.name == "张姐"
    assert saved.pet.name == "豆豆"
    assert saved.result == "已预约"


def test_push_task_records_channel_receiver_and_status(db_session, sample_records):
    from app.models import PushTask

    task = PushTask(
        store_id=sample_records["store"].id,
        follow_task_id=None,
        channel="wecom_internal",
        receiver_type="staff",
        receiver_id="zhang_staff",
        scene="repurchase_reminder",
        content="豆豆该洗护了，请跟进。",
    )
    db_session.add(task)
    db_session.commit()

    saved = db_session.query(PushTask).one()
    assert saved.status == "pending"
    assert saved.channel == "wecom_internal"
    assert saved.receiver_id == "zhang_staff"
