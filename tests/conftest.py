from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session():
    from app.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def sample_records(db_session):
    from app.models import Customer, Pet, ServiceRecord, Store

    store = Store(name="豆豆宠物店", owner_name="张店长", phone="13800000000", business_type="洗护")
    db_session.add(store)
    db_session.flush()

    customer = Customer(
        store_id=store.id,
        name="张姐",
        phone="13900000000",
        wechat_name="豆豆家长",
        last_visit_time=datetime.utcnow() - timedelta(days=24),
        visit_count=3,
        tags="老客",
    )
    db_session.add(customer)
    db_session.flush()

    pet = Pet(
        store_id=store.id,
        customer_id=customer.id,
        name="豆豆",
        pet_type="狗",
        breed="柯基",
        care_cycle_days=21,
        character_tags="怕吹风",
    )
    db_session.add(pet)
    db_session.flush()

    record = ServiceRecord(
        store_id=store.id,
        customer_id=customer.id,
        pet_id=pet.id,
        service_type="洗护",
        service_time=datetime.utcnow() - timedelta(days=24),
        amount=128,
        note="表现良好",
    )
    db_session.add(record)
    db_session.commit()
    return {"store": store, "customer": customer, "pet": pet, "record": record}
