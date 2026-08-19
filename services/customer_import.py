import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.models import Customer, Pet, ServiceRecord


COMMON_SERVICE_TYPES = {"洗护", "美容", "商品", "寄养"}
HEADER_ALIASES = {
    "name": ("客户姓名", "姓名", "客户", "name"),
    "phone": ("手机号", "手机", "电话", "phone"),
    "wechat_name": ("微信名", "微信", "wechat_name", "wechat"),
    "pet_name": ("宠物名", "宠物", "pet_name"),
    "pet_type": ("宠物类型", "类型", "pet_type"),
    "breed": ("品种", "breed"),
    "care_cycle_days": ("洗护周期天数", "洗护周期", "care_cycle_days"),
    "last_visit_time": ("最近到店", "上次到店", "last_visit_time"),
    "service_date": ("到店日期", "服务日期", "消费日期", "service_date"),
    "service_type": ("服务项目", "项目", "消费项目", "service_type"),
    "amount": ("消费金额", "金额", "amount"),
    "note": ("备注", "note"),
}

CUSTOMER_IMPORT_TEMPLATE = (
    "客户姓名,手机号,微信名,宠物名,宠物类型,品种,到店日期,服务项目,消费金额,备注\n"
    "张女士,13800000000,豆豆妈妈,豆豆,狗,比熊,2026-06-20,洗护,128,\n"
    "张女士,13800000000,豆豆妈妈,豆豆,狗,比熊,2026-06-20,商品,89,狗粮3kg\n"
    "李先生,13900000000,咪咪爸爸,咪咪,猫,英短,2026-06-18,美容,268,造型修剪\n"
)


def import_customers_from_csv(db_session, store_id: int, csv_path: str | Path) -> dict:
    result = {
        "created_customers": 0,
        "updated_customers": 0,
        "created_pets": 0,
        "created_service_records": 0,
        "skipped": 0,
        "total_amount": 0.0,
    }
    visit_dates_by_customer: dict[int, set[datetime.date]] = {}
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            data = {key: _pick(row, aliases) for key, aliases in HEADER_ALIASES.items()}
            if not data["name"]:
                result["skipped"] += 1
                continue
            service_time = _parse_datetime(data["service_date"]) or _parse_datetime(data["last_visit_time"])

            customer = _find_customer(db_session, store_id, data["phone"], data["name"])
            if customer is None:
                customer = Customer(
                    store_id=store_id,
                    name=data["name"],
                    phone=data["phone"] or None,
                    wechat_name=data["wechat_name"] or None,
                    last_visit_time=service_time,
                )
                db_session.add(customer)
                db_session.flush()
                result["created_customers"] += 1
            else:
                customer.name = data["name"] or customer.name
                customer.phone = data["phone"] or customer.phone
                customer.wechat_name = data["wechat_name"] or customer.wechat_name
                if service_time and (customer.last_visit_time is None or service_time > customer.last_visit_time):
                    customer.last_visit_time = service_time
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
                    db_session.flush()
                    result["created_pets"] += 1
                else:
                    pet.pet_type = data["pet_type"] or pet.pet_type
                    pet.breed = data["breed"] or pet.breed
                    if data["care_cycle_days"]:
                        pet.care_cycle_days = _parse_int(data["care_cycle_days"], default=pet.care_cycle_days)
                if service_time:
                    amount = _parse_amount(data["amount"])
                    service_type = _normalize_service_type(data["service_type"])
                    db_session.add(
                        ServiceRecord(
                            store_id=store_id,
                            customer_id=customer.id,
                            pet_id=pet.id,
                            service_type=service_type,
                            service_time=service_time,
                            amount=amount,
                            note=data["note"] or "CSV 导入生成",
                        )
                    )
                    customer.total_amount = Decimal(str(customer.total_amount or 0)) + amount
                    visit_dates_by_customer.setdefault(customer.id, set()).add(service_time.date())
                    result["created_service_records"] += 1
                    result["total_amount"] += float(amount)

    for customer_id, visit_dates in visit_dates_by_customer.items():
        customer = db_session.get(Customer, customer_id)
        if customer is not None:
            customer.visit_count = (customer.visit_count or 0) + len(visit_dates)
    db_session.commit()
    return result


def preview_customers_from_csv(csv_path: str | Path) -> dict:
    preview = {
        "total_rows": 0,
        "ready_rows": 0,
        "skipped_rows": 0,
        "estimated_new_customers": 0,
        "estimated_updated_customers": 0,
        "estimated_service_records": 0,
        "estimated_total_amount": 0.0,
        "issues": [],
    }
    seen_customers: set[str] = set()
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as file:
        for row_number, row in enumerate(csv.DictReader(file), start=2):
            preview["total_rows"] += 1
            data = {key: _pick(row, aliases) for key, aliases in HEADER_ALIASES.items()}
            if not data["name"]:
                preview["skipped_rows"] += 1
                preview["issues"].append(
                    {
                        "row_number": row_number,
                        "level": "error",
                        "field": "客户姓名",
                        "message": "缺少客户姓名，本行会被跳过",
                    }
                )
                continue

            preview["ready_rows"] += 1
            customer_key = data["phone"] or data["name"]
            if customer_key not in seen_customers:
                preview["estimated_new_customers"] += 1
                seen_customers.add(customer_key)
            else:
                preview["estimated_updated_customers"] += 1
            if data["care_cycle_days"] and _parse_int(data["care_cycle_days"], default=-1) < 0:
                preview["issues"].append(
                    {
                        "row_number": row_number,
                        "level": "warning",
                        "field": "洗护周期天数",
                        "message": "不是有效数字，导入时将按默认 21 天计算",
                    }
                )
            if data["last_visit_time"] and _parse_datetime(data["last_visit_time"]) is None:
                preview["issues"].append(
                    {
                        "row_number": row_number,
                        "level": "warning",
                        "field": "最近到店",
                        "message": "日期格式不正确，导入时不会生成洗护记录",
                    }
                )
            service_date = data["service_date"] or data["last_visit_time"]
            if service_date:
                if _parse_datetime(service_date) is None:
                    if data["service_date"]:
                        preview["issues"].append(
                            {
                                "row_number": row_number,
                                "level": "warning",
                                "field": "到店日期",
                                "message": "日期格式不正确，导入时不会生成消费记录",
                            }
                        )
                else:
                    preview["estimated_service_records"] += 1
                    preview["estimated_total_amount"] += float(_parse_amount(data["amount"]))
            if data["service_type"] and data["service_type"] not in COMMON_SERVICE_TYPES:
                preview["issues"].append(
                    {
                        "row_number": row_number,
                        "level": "warning",
                        "field": "服务项目",
                        "message": "不在常用服务项目中，导入时将归为其他",
                    }
                )
            if data["amount"] and _parse_amount(data["amount"], default=None) is None:
                preview["issues"].append(
                    {
                        "row_number": row_number,
                        "level": "warning",
                        "field": "消费金额",
                        "message": "不是有效数字，导入时将按 0 元记录",
                    }
                )
    return preview


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


def _parse_amount(value: str, default: Decimal | None = Decimal("0")) -> Decimal | None:
    if not value:
        return default
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return default


def _normalize_service_type(value: str) -> str:
    if not value:
        return "洗护"
    return value if value in COMMON_SERVICE_TYPES else "其他"
