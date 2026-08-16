from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from string import Formatter

from app.models import ContentItem, Customer, Pet, ServiceRecord, Store


TEMPLATE_ROOT = Path(__file__).with_name("templates")


def load_template(template_code: str) -> dict:
    for path in TEMPLATE_ROOT.rglob("*.yaml"):
        template = _parse_simple_yaml(path.read_text(encoding="utf-8"))
        if template.get("code") == template_code:
            return template
    raise ValueError(f"Template {template_code} not found")


def list_templates() -> list[dict]:
    templates = []
    for path in sorted(TEMPLATE_ROOT.rglob("*.yaml")):
        template = _parse_simple_yaml(path.read_text(encoding="utf-8"))
        template["path"] = str(path.relative_to(TEMPLATE_ROOT))
        templates.append(template)
    return templates


def auto_fill_variables(template_code: str, store_id: int, session) -> dict:
    store = session.get(Store, store_id)
    record = (
        session.query(ServiceRecord)
        .filter_by(store_id=store_id)
        .order_by(ServiceRecord.service_time.desc(), ServiceRecord.id.desc())
        .first()
    )
    customer = session.get(Customer, record.customer_id) if record else None
    pet = session.get(Pet, record.pet_id) if record else None
    return {
        "store_name": store.name if store else "AIPet Store",
        "customer_name": customer.name if customer else "pet parent",
        "pet_name": pet.name if pet else "pet",
        "breed": pet.breed if pet and pet.breed else "pet",
        "service_type": record.service_type if record else "grooming",
        "service_date": record.service_time.date().isoformat() if record else date.today().isoformat(),
        "template_code": template_code,
    }


def render_template(template: dict, variables: dict) -> dict:
    safe_vars = _DefaultDict(variables)
    return {
        "title": template.get("title", "").format_map(safe_vars),
        "body": template.get("body", "").format_map(safe_vars),
        "hashtags": template.get("hashtags", []),
        "image_prompt": template.get("image_prompt", "").format_map(safe_vars),
    }


def generate_content_item(session, store_id: int, template_code: str, scheduled_date: date | None = None) -> ContentItem:
    template = load_template(template_code)
    values = auto_fill_variables(template_code, store_id, session)
    rendered = render_template(template, values)
    item = ContentItem(
        store_id=store_id,
        channel=template.get("channel", "moments"),
        topic=template.get("topic", template_code),
        title=rendered["title"],
        body=rendered["body"],
        hashtags=",".join(rendered["hashtags"]),
        image_prompt=rendered["image_prompt"] or _fallback_image_prompt(template_code, values),
        scheduled_date=scheduled_date,
        scheduled_at=datetime.combine(scheduled_date, datetime.min.time()) if scheduled_date else None,
        interaction_data=json.dumps({"likes": 0, "comments": 0, "shares": 0, "consultations": 0}),
        status="draft",
    )
    session.add(item)
    session.commit()
    return item


def _fallback_image_prompt(template_code: str, variables: dict) -> str:
    return f"Editable image prompt for {template_code}: {variables.get('pet_name')} at {variables.get('store_name')}"


def _parse_simple_yaml(raw: str) -> dict:
    result: dict[str, object] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key:
            result.setdefault(current_key, [])
            assert isinstance(result[current_key], list)
            result[current_key].append(_unquote(line.strip()[2:].strip()))
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            result[key] = [] if value == "" else _unquote(value)
    return result


def _unquote(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


class _DefaultDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"
