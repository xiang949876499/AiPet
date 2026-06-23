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


def test_preview_customer_import_reports_row_issues_without_writing(db_session, tmp_path, sample_records):
    from app.models import Customer
    from services.customer_import import preview_customers_from_csv

    before_count = db_session.query(Customer).count()
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "客户姓名,手机号,微信名,宠物名,宠物类型,品种,洗护周期天数,最近到店\n"
        "刘女士,13300000000,花花妈妈,花花,猫,橘猫,abc,2026-06-01\n"
        ",13200000000,空名客户,豆豆,狗,柯基,21,2026-06-02\n"
        "周老板,13100000000,元宝爸爸,元宝,狗,金毛,30,2026/99/99\n",
        encoding="utf-8-sig",
    )

    preview = preview_customers_from_csv(csv_path)

    assert preview["total_rows"] == 3
    assert preview["ready_rows"] == 2
    assert preview["skipped_rows"] == 1
    assert preview["issues"] == [
        {"row_number": 2, "level": "warning", "field": "洗护周期天数", "message": "不是有效数字，导入时将按默认 21 天计算"},
        {"row_number": 3, "level": "error", "field": "客户姓名", "message": "缺少客户姓名，本行会被跳过"},
        {"row_number": 4, "level": "warning", "field": "最近到店", "message": "日期格式不正确，导入时不会生成洗护记录"},
    ]
    assert db_session.query(Customer).count() == before_count
