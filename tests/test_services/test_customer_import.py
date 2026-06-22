from datetime import datetime


def test_import_customers_from_csv_creates_customers_and_pets(db_session, tmp_path, sample_records):
    from app.models import Customer, Pet
    from services.customer_import import import_customers_from_csv

    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "李老板,13700000000,旺财家长,旺财,狗,泰迪,30,2026-06-01\n"
        "王女士,13600000000,煤球妈妈,煤球,猫,英短,45,2026-05-20\n",
        encoding="utf-8-sig",
    )

    result = import_customers_from_csv(db_session, sample_records["store"].id, csv_path)

    assert result == {
        "created_customers": 2,
        "updated_customers": 0,
        "created_pets": 2,
        "skipped": 0,
    }
    assert db_session.query(Customer).filter_by(phone="13700000000").one().wechat_name == "旺财家长"
    pet = db_session.query(Pet).filter_by(name="旺财").one()
    assert pet.care_cycle_days == 30
    assert pet.breed == "泰迪"


def test_import_customers_from_csv_updates_existing_customer_without_duplicate(db_session, tmp_path, sample_records):
    from app.models import Customer, Pet
    from services.customer_import import import_customers_from_csv

    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "李老板,13700000000,旺财家长,旺财,狗,泰迪,30,2026-06-01\n",
        encoding="utf-8",
    )
    import_customers_from_csv(db_session, sample_records["store"].id, csv_path)

    csv_path.write_text(
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "李老板,13700000000,旺财新微信,旺财,狗,泰迪,25,2026-06-10\n",
        encoding="utf-8",
    )
    result = import_customers_from_csv(db_session, sample_records["store"].id, csv_path)

    assert result["created_customers"] == 0
    assert result["updated_customers"] == 1
    assert result["created_pets"] == 0
    customer = db_session.query(Customer).filter_by(phone="13700000000").one()
    assert customer.wechat_name == "旺财新微信"
    assert customer.last_visit_time.date() == datetime(2026, 6, 10).date()
    assert db_session.query(Pet).filter_by(name="旺财").count() == 1
