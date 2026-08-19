import json
from datetime import date, datetime, timedelta

from agents.content import ContentAgent
from app.models import (
    Appointment,
    ContentItem,
    Customer,
    FollowTask,
    OutreachLog,
    Pet,
    Product,
    ProductPurchase,
    PushTask,
    SampleTrial,
    ServiceRecord,
    Staff,
    Store,
    StoreSubscription,
    OutreachRule,
)
from services.subscriptions import ensure_store_subscription, seed_subscription_plans


DEMO_STORE_NAME = "豆豆宠物店"


def seed_demo_data(session, refresh: bool = False):
    existing_demo_store = session.query(Store).filter_by(name=DEMO_STORE_NAME).order_by(Store.id.asc()).first()
    if refresh and existing_demo_store is not None:
        _clear_demo_store(session, existing_demo_store)
        session.commit()
    elif session.query(Store).count() > 0:
        return {"created": 0}

    now = datetime.utcnow()
    store = Store(
        name=DEMO_STORE_NAME,
        owner_name="张店长",
        phone="13800000000",
        address="上海市徐汇区桂平路 188 号",
        business_type="洗护美容综合店",
    )
    session.add(store)
    session.flush()

    staff_by_key = _seed_staff(session, store.id, now)
    seed_subscription_plans(session)
    ensure_store_subscription(session, store.id)
    from outreach.rules import _ensure_default_rules

    _ensure_default_rules(session, store.id)

    product_by_key = _seed_products(session, store.id)
    customer_rows = _seed_customers_and_pets(session, store.id, now)
    _seed_service_records(session, store.id, customer_rows, staff_by_key, now)
    _seed_product_purchases(session, store.id, customer_rows, product_by_key, now)
    _seed_sample_trials(session, store.id, customer_rows, product_by_key, now)
    _seed_appointments(session, store.id, customer_rows, staff_by_key, now)
    _seed_content_items(session, store.id, now)
    _seed_outreach_history(session, store.id, customer_rows, now)
    _seed_manual_work(session, store.id, customer_rows, staff_by_key, now)

    session.commit()
    ContentAgent(session).execute({"store_id": store.id})
    return {"created": len(customer_rows)}


def _clear_demo_store(session, store: Store) -> None:
    store_id = store.id
    for model in (
        PushTask,
        OutreachLog,
        FollowTask,
        ProductPurchase,
        SampleTrial,
        Appointment,
        ServiceRecord,
        Product,
        Pet,
        Customer,
        Staff,
        ContentItem,
        OutreachRule,
        StoreSubscription,
    ):
        session.query(model).filter_by(store_id=store_id).delete(synchronize_session=False)
    session.delete(store)


def _seed_staff(session, store_id: int, now: datetime) -> dict[str, Staff]:
    staff_specs = [
        ("wang", "小王", "店员", "13800000001", "wang", 1),
        ("lin", "林美容师", "美容师", "13800000002", "lin_groomer", 18),
        ("chen", "陈顾问", "客户运营", "13800000003", "chen_ops", 7),
    ]
    staff_by_key = {}
    for key, name, role, phone, wecom_userid, bound_days in staff_specs:
        staff = Staff(
            store_id=store_id,
            name=name,
            role=role,
            phone=phone,
            status="启用",
            wecom_userid=wecom_userid,
            wecom_name=name,
            wecom_bound_at=now - timedelta(days=bound_days),
        )
        session.add(staff)
        staff_by_key[key] = staff
    session.flush()
    return staff_by_key


def _seed_products(session, store_id: int) -> dict[str, Product]:
    products = [
        ("salmon_food", "海洋三文鱼全价粮", "主粮", "犬猫通用 2kg", 168, 35),
        ("probiotic", "肠胃舒益生菌", "营养品", "30 袋", 98, 30),
        ("low_scent_shampoo", "低敏留香沐浴露", "洗护用品", "500ml", 88, 45),
        ("tooth_gel", "口腔护理凝胶", "日常护理", "60g", 68, 28),
        ("sample_pack", "换粮体验试用装", "试用装", "50g x 3", 0, 7),
    ]
    product_by_key = {}
    for key, name, category, spec, price, cycle in products:
        product = Product(
            store_id=store_id,
            name=name,
            category=category,
            spec=spec,
            price=price,
            consume_cycle_days=cycle,
            status="上架",
        )
        session.add(product)
        product_by_key[key] = product
    session.flush()
    return product_by_key


def _seed_customers_and_pets(session, store_id: int, now: datetime) -> list[dict]:
    rows = [
        {
            "customer": "张姐",
            "phone": "13900000000",
            "wechat": "豆豆家长",
            "source": "老客转介绍",
            "tags": "老客,洗护到期,适合会员卡",
            "pet": "豆豆",
            "pet_type": "狗",
            "breed": "柯基",
            "gender": "妹妹",
            "birthday": date(2022, 5, 14),
            "weight": 11.2,
            "hair_type": "短毛",
            "character_tags": "怕吹风,亲人",
            "cycle": 21,
            "days_ago": 24,
            "visit_count": 5,
            "total_amount": 936,
            "note": "洗护前先确认是否需要低敏香波。",
        },
        {
            "customer": "李先生",
            "phone": "13900000001",
            "wechat": "奶茶爸爸",
            "source": "小红书",
            "tags": "猫咪客户,高客单",
            "pet": "奶茶",
            "pet_type": "猫",
            "breed": "布偶",
            "gender": "弟弟",
            "birthday": date(2021, 11, 3),
            "weight": 5.6,
            "hair_type": "长毛",
            "character_tags": "胆小,怕陌生人",
            "cycle": 30,
            "days_ago": 62,
            "visit_count": 3,
            "total_amount": 684,
            "note": "到店时尽量安排安静房间。",
        },
        {
            "customer": "王姐",
            "phone": "13900000002",
            "wechat": "小七妈妈",
            "source": "门店自然客流",
            "tags": "高频老客,会员",
            "pet": "小七",
            "pet_type": "狗",
            "breed": "柴犬",
            "gender": "妹妹",
            "birthday": date(2020, 8, 21),
            "weight": 9.4,
            "hair_type": "双层毛",
            "character_tags": "爱掉毛,配合度高",
            "cycle": 21,
            "days_ago": 18,
            "visit_count": 8,
            "total_amount": 1512,
            "note": "常买除味护理，适合推会员日。",
        },
        {
            "customer": "赵哥",
            "phone": "13900000003",
            "wechat": "可乐爸",
            "source": "大众点评",
            "tags": "沉睡客户,大型犬",
            "pet": "可乐",
            "pet_type": "狗",
            "breed": "金毛",
            "gender": "弟弟",
            "birthday": date(2019, 2, 17),
            "weight": 29.5,
            "hair_type": "长毛",
            "character_tags": "亲人,洗澡爱动",
            "cycle": 30,
            "days_ago": 95,
            "visit_count": 2,
            "total_amount": 476,
            "note": "大狗洗护需要提前预留 2 小时。",
        },
        {
            "customer": "陈女士",
            "phone": "13900000004",
            "wechat": "花卷家长",
            "source": "抖音团购",
            "tags": "新客,待二次到店",
            "pet": "花卷",
            "pet_type": "猫",
            "breed": "英短",
            "gender": "妹妹",
            "birthday": date(2023, 3, 6),
            "weight": 4.2,
            "hair_type": "短毛",
            "character_tags": "怕水,需要安抚",
            "cycle": 30,
            "days_ago": 12,
            "visit_count": 1,
            "total_amount": 138,
            "note": "首次到店体验不错，适合 14 天后做关怀。",
        },
        {
            "customer": "刘老板",
            "phone": "13900000005",
            "wechat": "皮蛋老板",
            "source": "社群活动",
            "tags": "高频老客,喜欢套餐",
            "pet": "皮蛋",
            "pet_type": "狗",
            "breed": "泰迪",
            "gender": "弟弟",
            "birthday": date(2020, 12, 1),
            "weight": 6.8,
            "hair_type": "卷毛",
            "character_tags": "美容常客,怕剪指甲",
            "cycle": 28,
            "days_ago": 35,
            "visit_count": 9,
            "total_amount": 2260,
            "note": "美容偏好圆脸造型。",
        },
        {
            "customer": "周小姐",
            "phone": "13900000006",
            "wechat": "糯米姐姐",
            "source": "朋友推荐",
            "tags": "沉睡客户,猫咪客户",
            "pet": "糯米",
            "pet_type": "猫",
            "breed": "缅因",
            "gender": "妹妹",
            "birthday": date(2019, 9, 27),
            "weight": 7.1,
            "hair_type": "长毛",
            "character_tags": "毛结多,不爱出门",
            "cycle": 45,
            "days_ago": 155,
            "visit_count": 2,
            "total_amount": 616,
            "note": "曾反馈停车不方便，触达时先做关怀。",
        },
        {
            "customer": "孙阿姨",
            "phone": "13900000007",
            "wechat": "旺财奶奶",
            "source": "门店自然客流",
            "tags": "稳定老客,高频",
            "pet": "旺财",
            "pet_type": "狗",
            "breed": "比熊",
            "gender": "弟弟",
            "birthday": date(2018, 6, 30),
            "weight": 7.8,
            "hair_type": "卷毛",
            "character_tags": "安静,需慢吹",
            "cycle": 21,
            "days_ago": 8,
            "visit_count": 12,
            "total_amount": 3120,
            "note": "习惯上午到店。",
        },
        {
            "customer": "高先生",
            "phone": "13900000008",
            "wechat": "来福爸",
            "source": "企业微信",
            "tags": "运动犬,洗护到期",
            "pet": "来福",
            "pet_type": "狗",
            "breed": "边牧",
            "gender": "弟弟",
            "birthday": date(2021, 4, 9),
            "weight": 18.6,
            "hair_type": "中长毛",
            "character_tags": "精力旺盛,爱玩水",
            "cycle": 30,
            "days_ago": 43,
            "visit_count": 4,
            "total_amount": 1060,
            "note": "洗后建议提醒补充驱虫。",
        },
        {
            "customer": "林女士",
            "phone": "13900000009",
            "wechat": "布丁妈妈",
            "source": "大众点评",
            "tags": "免打扰,猫咪客户",
            "pet": "布丁",
            "pet_type": "猫",
            "breed": "橘猫",
            "gender": "弟弟",
            "birthday": date(2022, 1, 19),
            "weight": 6.3,
            "hair_type": "短毛",
            "character_tags": "怕生,不喜欢电话",
            "cycle": 30,
            "days_ago": 2,
            "visit_count": 2,
            "total_amount": 236,
            "do_not_disturb": True,
            "dnd_channels": "wecom_external",
            "dnd_message_types": "marketing",
            "note": "家长要求本周不主动联系。",
        },
        {
            "customer": "何小姐",
            "phone": "13900000010",
            "wechat": "小满妈妈",
            "source": "小红书",
            "tags": "洗护到期,可转化套餐",
            "pet": "小满",
            "pet_type": "狗",
            "breed": "博美",
            "gender": "妹妹",
            "birthday": date(2023, 7, 12),
            "weight": 3.4,
            "hair_type": "长毛",
            "character_tags": "泪痕护理,爱叫",
            "cycle": 21,
            "days_ago": 27,
            "visit_count": 3,
            "total_amount": 594,
            "note": "上次咨询过泪痕护理套餐。",
        },
        {
            "customer": "马先生",
            "phone": "13900000011",
            "wechat": "肉松爸",
            "source": "社群活动",
            "tags": "复购风险,美容客户",
            "pet": "肉松",
            "pet_type": "狗",
            "breed": "雪纳瑞",
            "gender": "弟弟",
            "birthday": date(2020, 10, 8),
            "weight": 8.1,
            "hair_type": "刚毛",
            "character_tags": "美容周期长,不爱剃脚底",
            "cycle": 35,
            "days_ago": 74,
            "visit_count": 3,
            "total_amount": 940,
            "note": "上次剪毛满意，可提醒保持造型。",
        },
    ]

    seeded_rows = []
    for item in rows:
        customer = Customer(
            store_id=store_id,
            name=item["customer"],
            phone=item["phone"],
            wechat_name=item["wechat"],
            source=item["source"],
            tags=item["tags"],
            last_visit_time=now - timedelta(days=item["days_ago"]),
            total_amount=item["total_amount"],
            visit_count=item["visit_count"],
            do_not_disturb=item.get("do_not_disturb", False),
            dnd_channels=item.get("dnd_channels"),
            dnd_message_types=item.get("dnd_message_types"),
            push_consent_status="opted_in" if not item.get("do_not_disturb") else "paused",
            external_userid=f"wm_{item['phone'][-4:]}",
            note=item["note"],
        )
        session.add(customer)
        session.flush()
        pet = Pet(
            store_id=store_id,
            customer_id=customer.id,
            name=item["pet"],
            pet_type=item["pet_type"],
            breed=item["breed"],
            gender=item["gender"],
            birthday=item["birthday"],
            vaccine_next_date=date.today() + timedelta(days=30 + len(seeded_rows) * 3),
            deworming_last_date=date.today() - timedelta(days=22 + len(seeded_rows)),
            weight=item["weight"],
            hair_type=item["hair_type"],
            character_tags=item["character_tags"],
            care_cycle_days=item["cycle"],
            note=item["note"],
        )
        session.add(pet)
        session.flush()
        seeded_rows.append({"customer": customer, "pet": pet, "spec": item})
    return seeded_rows


def _seed_service_records(session, store_id: int, rows: list[dict], staff_by_key: dict[str, Staff], now: datetime) -> None:
    service_mix = {
        "张姐": [("洗护", 24, 168), ("洗护", 52, 168), ("洁牙护理", 83, 98)],
        "李先生": [("洗护", 62, 198), ("猫咪精洗", 103, 268)],
        "王姐": [("洗护", 18, 158), ("洗护", 43, 158), ("除味护理", 66, 128)],
        "赵哥": [("洗护", 95, 238), ("美容", 142, 298)],
        "陈女士": [("洗护", 12, 138)],
        "刘老板": [("美容", 35, 298), ("洗护", 66, 168), ("美容", 96, 298)],
        "周小姐": [("猫咪精洗", 155, 308), ("去毛结护理", 211, 308)],
        "孙阿姨": [("洗护", 8, 168), ("洗护", 29, 168), ("美容", 58, 268)],
        "高先生": [("洗护", 43, 188), ("驱虫护理", 75, 128)],
        "林女士": [("洗护", 2, 118), ("洗护", 39, 118)],
        "何小姐": [("洗护", 27, 168), ("泪痕护理", 51, 98)],
        "马先生": [("美容", 74, 328), ("洗护", 121, 168)],
    }
    notes = {
        "洗护": "洗护完成，毛发状态良好，建议按周期预约。",
        "美容": "造型完成，家长满意，下次可提前预留美容师。",
        "猫咪精洗": "猫咪精洗完成，吹干过程需要耐心安抚。",
        "洁牙护理": "口腔护理完成，建议配合居家护理凝胶。",
        "除味护理": "除味护理完成，适合夏季持续维护。",
        "去毛结护理": "毛结较多，建议缩短梳毛周期。",
        "驱虫护理": "体外驱虫完成，下次按月提醒。",
        "泪痕护理": "泪痕护理完成，建议复购护理湿巾。",
    }
    staff_cycle = [staff_by_key["wang"], staff_by_key["lin"], staff_by_key["chen"]]
    for row in rows:
        customer = row["customer"]
        pet = row["pet"]
        for index, (service_type, days_ago, amount) in enumerate(service_mix[customer.name]):
            service_time = now - timedelta(days=days_ago, hours=index)
            session.add(
                ServiceRecord(
                    store_id=store_id,
                    customer_id=customer.id,
                    pet_id=pet.id,
                    service_type=service_type,
                    service_time=service_time,
                    amount=amount,
                    staff_id=staff_cycle[index % len(staff_cycle)].id,
                    next_suggest_time=service_time + timedelta(days=pet.care_cycle_days),
                    note=notes.get(service_type, "服务完成，建议按周期维护。"),
                )
            )


def _seed_product_purchases(
    session,
    store_id: int,
    rows: list[dict],
    product_by_key: dict[str, Product],
    now: datetime,
) -> None:
    purchase_specs = [
        ("张姐", "low_scent_shampoo", 1, 88, 18),
        ("李先生", "probiotic", 2, 196, 31),
        ("王姐", "tooth_gel", 1, 68, 10),
        ("孙阿姨", "salmon_food", 1, 168, 20),
        ("何小姐", "tooth_gel", 1, 68, 24),
    ]
    row_by_customer = {row["customer"].name: row for row in rows}
    for customer_name, product_key, quantity, amount, days_ago in purchase_specs:
        row = row_by_customer[customer_name]
        product = product_by_key[product_key]
        purchased_at = now - timedelta(days=days_ago)
        session.add(
            ProductPurchase(
                store_id=store_id,
                customer_id=row["customer"].id,
                pet_id=row["pet"].id,
                product_id=product.id,
                purchase_time=purchased_at,
                quantity=quantity,
                amount=amount,
                next_remind_time=purchased_at + timedelta(days=product.consume_cycle_days),
            )
        )


def _seed_sample_trials(
    session,
    store_id: int,
    rows: list[dict],
    product_by_key: dict[str, Product],
    now: datetime,
) -> None:
    row_by_customer = {row["customer"].name: row for row in rows}
    trial_specs = [
        ("陈女士", "sample_pack", 2, None, False, 0),
        ("高先生", "probiotic", 4, "反馈不错，狗狗愿意吃", True, 98),
        ("马先生", "sample_pack", 1, None, False, 0),
    ]
    for customer_name, product_key, days_ago, feedback, converted, converted_amount in trial_specs:
        row = row_by_customer[customer_name]
        session.add(
            SampleTrial(
                store_id=store_id,
                customer_id=row["customer"].id,
                pet_id=row["pet"].id,
                product_id=product_by_key[product_key].id,
                receive_time=now - timedelta(days=days_ago),
                follow_time=now - timedelta(days=1) if feedback else None,
                feedback=feedback,
                converted=converted,
                converted_amount=converted_amount,
            )
        )


def _seed_appointments(
    session,
    store_id: int,
    rows: list[dict],
    staff_by_key: dict[str, Staff],
    now: datetime,
) -> None:
    row_by_customer = {row["customer"].name: row for row in rows}
    today = now.replace(hour=9, minute=0, second=0, microsecond=0)
    appointment_specs = [
        ("孙阿姨", "洗护", today + timedelta(hours=1), 90, "已确认", "老客上午到店，安排慢吹。", "wang"),
        ("何小姐", "泪痕护理", today + timedelta(hours=3), 60, "待确认", "先确认是否加做眼周护理。", "chen"),
        ("张姐", "洗护", today + timedelta(days=1, hours=2), 90, "已确认", "使用低敏香波。", "lin"),
        ("刘老板", "美容", today + timedelta(days=2, hours=4), 120, "待确认", "圆脸造型，预留美容师。", "lin"),
        ("陈女士", "二次到店体验", today + timedelta(days=4, hours=2), 60, "已预约", "新客二次到店。", "chen"),
    ]
    for customer_name, service_type, start, duration, status, note, staff_key in appointment_specs:
        row = row_by_customer[customer_name]
        session.add(
            Appointment(
                store_id=store_id,
                customer_id=row["customer"].id,
                pet_id=row["pet"].id,
                service_type=service_type,
                start_time=start,
                end_time=start + timedelta(minutes=duration),
                staff_id=staff_by_key[staff_key].id,
                status=status,
                note=note,
            )
        )


def _seed_content_items(session, store_id: int, now: datetime) -> None:
    content_specs = [
        (
            "朋友圈",
            "洗护到期客户关怀",
            "本周洗护小提醒",
            "最近天气闷热，短鼻犬和长毛猫更容易打结、出油。已经到周期的家长可以提前约个清爽洗护。",
            "draft",
            0,
            {"likes": 18, "comments": 3, "shares": 1, "consultations": 2},
        ),
        (
            "小红书",
            "夏季护理知识",
            "长毛猫夏天一定要剃毛吗？",
            "不一定。比起直接剃短，更建议先看毛结、皮肤状态和猫咪应激程度，再决定护理方案。",
            "published",
            1,
            {"likes": 86, "comments": 12, "shares": 8, "consultations": 5},
        ),
        (
            "短视频脚本",
            "门店服务案例",
            "怕吹风的小狗洗护流程",
            "镜头 1：进店安抚；镜头 2：低噪吹风；镜头 3：家长验收；结尾引导预约本周空档。",
            "draft",
            2,
            {"likes": 0, "comments": 0, "shares": 0, "consultations": 0},
        ),
        (
            "朋友圈",
            "客户好评",
            "可乐上次洗护反馈",
            "大型犬洗护建议提前预约，门店会预留更宽松的时段和双人配合。",
            "published",
            -2,
            {"likes": 32, "comments": 5, "shares": 2, "consultations": 3},
        ),
    ]
    for channel, topic, title, body, status, day_offset, interactions in content_specs:
        scheduled = date.today() + timedelta(days=day_offset)
        session.add(
            ContentItem(
                store_id=store_id,
                channel=channel,
                topic=topic,
                title=title,
                body=body,
                hashtags="#宠物洗护 #宠物门店 #科学护理",
                image_prompt=f"真实宠物门店场景，主题：{title}",
                scheduled_date=scheduled,
                interaction_data=json.dumps(interactions, ensure_ascii=False),
                status=status,
                scheduled_at=now + timedelta(days=day_offset, hours=2),
                published_at=now + timedelta(days=day_offset, hours=4) if status == "published" else None,
                created_at=now + timedelta(days=day_offset),
            )
        )


def _seed_outreach_history(session, store_id: int, rows: list[dict], now: datetime) -> None:
    row_by_customer = {row["customer"].name: row for row in rows}
    history_specs = [
        ("王姐", "member_care", "sent", 2, "这周有会员日，小七常用护理可以一起安排。", "想约周末", True, 158),
        ("陈女士", "new_customer_second_visit", "sent", 1, "花卷上次首次体验还适应吗？这周可以帮您留一个安静时段。", "可以看看周五", False, 0),
        ("刘老板", "grooming_due", "sent", 6, "皮蛋的造型周期差不多到了，要不要提前留林美容师？", "下周再约", True, 298),
        ("赵哥", "dormant_wake", "pending_confirm", 0, "赵哥，好久没见可乐啦，最近毛发状态怎么样？", None, False, 0),
    ]
    for customer_name, rule_code, status, days_ago, content, response, converted, revenue in history_specs:
        row = row_by_customer[customer_name]
        sent_at = now - timedelta(days=days_ago, hours=2) if status == "sent" else None
        response_time = sent_at + timedelta(hours=3) if sent_at and response else None
        decision_card = {
            "customer": row["customer"].name,
            "pet": row["pet"].name,
            "reason": "基于最近服务周期和客户标签生成",
            "recommended_action": "老板确认后再发送",
        }
        session.add(
            OutreachLog(
                store_id=store_id,
                customer_id=row["customer"].id,
                pet_id=row["pet"].id,
                rule_code=rule_code,
                channel="wecom_external",
                message_type="service",
                send_mode="manual_confirm",
                content=content,
                status=status,
                decision_card=json.dumps(decision_card, ensure_ascii=False),
                sent_at=sent_at,
                response_time=response_time,
                response_content=response,
                appointment_created=converted,
                appointment_time=sent_at + timedelta(days=2) if converted and sent_at else None,
                service_within_7d=converted,
                attributed_revenue=revenue,
                created_at=now - timedelta(days=days_ago, hours=3),
            )
        )


def _seed_manual_work(
    session,
    store_id: int,
    rows: list[dict],
    staff_by_key: dict[str, Staff],
    now: datetime,
) -> None:
    row_by_customer = {row["customer"].name: row for row in rows}
    manual_specs = [
        ("陈女士", "试用装回访", "中", "客户领取换粮试用装已超过 24 小时", "询问适口性并记录反馈", "待处理"),
        ("王姐", "会员关怀", "低", "高频老客最近 30 天到店 2 次", "发送会员日护理建议", "已发送"),
    ]
    first_pending_task = None
    for customer_name, task_type, priority, reason, action, status in manual_specs:
        row = row_by_customer[customer_name]
        task = FollowTask(
            store_id=store_id,
            customer_id=row["customer"].id,
            pet_id=row["pet"].id,
            task_type=task_type,
            priority=priority,
            reason=reason,
            suggested_action=action,
            due_date=now,
            status=status,
            ai_message=_manual_message(row["customer"].name, row["pet"].name, task_type),
            result="已回复" if status == "已发送" else None,
            created_at=now - timedelta(hours=2),
        )
        session.add(task)
        session.flush()
        if status == "待处理" and first_pending_task is None:
            first_pending_task = task

    if first_pending_task is not None:
        session.add(
            PushTask(
                store_id=store_id,
                follow_task_id=first_pending_task.id,
                channel="wecom_internal",
                receiver_type="staff",
                receiver_id=staff_by_key["wang"].wecom_userid,
                scene="sample_followup",
                content=(
                    f"客户：{first_pending_task.customer.name}\n"
                    f"宠物：{first_pending_task.pet.name}\n"
                    f"原因：{first_pending_task.reason}\n"
                    f"建议：{first_pending_task.suggested_action}"
                ),
                status="pending",
                scheduled_at=now + timedelta(minutes=30),
            )
        )


def _manual_message(customer_name: str, pet_name: str, task_type: str) -> str:
    if task_type == "试用装回访":
        return f"{customer_name}，想问下{pet_name}带回家的试用装有试吃吗？适口性怎么样呀？"
    return f"{customer_name}，这周店里有老客护理日，{pet_name}常做的项目可以提前帮您留时间。"
