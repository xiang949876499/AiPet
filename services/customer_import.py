import csv
from datetime import datetime
from pathlib import Path

from app.models import Customer, Pet


HEADER_ALIASES = {
    "name": ("客户姓名", "姓名", "客户", "name"),
    "phone": ("手机号", "手机", "电话", "phone"),
    "wechat_name": ("微信名", "微信", "wechat_name", "wechat"),
    "pet_name": ("宠物名", "宠物", "pet_name"),
    "pet_type": ("宠物类型", "类型", "pet_type"),
    "breed": ("品种", "breed"),
    "care_cycle_days": ("洗护周期天数", "洗护周期", "care_cycle_days"),
    "last_visit_time": ("最近到店", "上次到店", "last_visit_time"),
}


def import_customers_from_csv(db_session, store_id: int, csv_path: str | Path) -> dict:
    result = {"created_customers": 0, "updated_customers": 0, "created_pets": 0, "skipped": 0}
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            data = {key: _pick(row, aliases) for key, aliases in HEADER_ALIASES.items()}
            if not data["name"]:
                result["skipped"] += 1
                continue

            customer = _find_customer(db_session, store_id, data["phone"], data["name"])
            if customer is None:
                customer = Customer(
                    store_id=store_id,
                    name=data["name"],
                    phone=data["phone"] or None,
                    wechat_name=data["wechat_name"] or None,
                    last_visit_time=_parse_datetime(data["last_visit_time"]),
                )
                db_session.add(customer)
                db_session.flush()
                result["created_customers"] += 1
            else:
                customer.name = data["name"] or customer.name
                customer.phone = data["phone"] or customer.phone
                customer.wechat_name = data["wechat_name"] or customer.wechat_name
                customer.last_visit_time = _parse_datetime(data["last_visit_time"]) or customer.last_visit_time
                result["updated_customers"] += 1

            if data["pet_name"]:
                pet = (
                    db_session.query(Pet)
                    .filter_by(store_id=store_id, customer_id=customer.id, name=data["pet_name"])
                    .one_or_none()
                )
                if pet is None:
                    pet = Pet(
                        store_id=store_id,
                        customer_id=customer.id,
                        name=data["pet_name"],
                        pet_type=data["pet_type"] or "狗",
                        breed=data["breed"] or None,
                        care_cycle_days=_parse_int(data["care_cycle_days"], default=21),
                    )
                    db_session.add(pet)
                    result["created_pets"] += 1
                else:
                    pet.pet_type = data["pet_type"] or pet.pet_type
                    pet.breed = data["breed"] or pet.breed
                    pet.care_cycle_days = _parse_int(data["care_cycle_days"], default=pet.care_cycle_days)

    db_session.commit()
    return result


def _find_customer(db_session, store_id: int, phone: str, name: str) -> Customer | None:
    if phone:
        customer = db_session.query(Customer).filter_by(store_id=store_id, phone=phone).one_or_none()
        if customer is not None:
            return customer
    return db_session.query(Customer).filter_by(store_id=store_id, name=name).one_or_none()


def _pick(row: dict, aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = row.get(alias)
        if value:
            return value.strip()
    return ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
