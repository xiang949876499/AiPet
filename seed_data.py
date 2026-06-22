from datetime import datetime, timedelta

from app.models import Customer, Pet, ServiceRecord, Staff, Store
from agents.content import ContentAgent
from services.subscriptions import ensure_store_subscription, seed_subscription_plans


def seed_demo_data(session):
    if session.query(Store).count() > 0:
        return {"created": 0}

    store = Store(name="豆豆宠物店", owner_name="张店长", phone="13800000000", business_type="洗护")
    session.add(store)
    session.flush()

    session.add(Staff(store_id=store.id, name="小王", role="店员", phone="13800000001", wecom_userid="wang"))
    seed_subscription_plans(session)
    ensure_store_subscription(session, store.id)

    customers = [
        ("张姐", "豆豆", "狗", "柯基", 24, 21),
        ("李先生", "奶茶", "猫", "布偶", 62, 30),
        ("王姐", "小七", "狗", "柴犬", 18, 21),
        ("赵哥", "可乐", "狗", "金毛", 95, 30),
    ]
    for customer_name, pet_name, pet_type, breed, days_ago, cycle in customers:
        customer = Customer(
            store_id=store.id,
            name=customer_name,
            phone="13900000000",
            wechat_name=f"{pet_name}家长",
            last_visit_time=datetime.utcnow() - timedelta(days=days_ago),
            visit_count=2,
        )
        session.add(customer)
        session.flush()
        pet = Pet(
            store_id=store.id,
            customer_id=customer.id,
            name=pet_name,
            pet_type=pet_type,
            breed=breed,
            care_cycle_days=cycle,
        )
        session.add(pet)
        session.flush()
        session.add(
            ServiceRecord(
                store_id=store.id,
                customer_id=customer.id,
                pet_id=pet.id,
                service_type="洗护",
                service_time=datetime.utcnow() - timedelta(days=days_ago),
                amount=128,
            )
        )

    session.commit()
    ContentAgent(session).execute({"store_id": store.id})
    return {"created": len(customers)}
