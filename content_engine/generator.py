from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from string import Formatter

from app.models import ContentItem, Customer, Pet, ServiceRecord, Store
from core.llm import LLMClient


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


def generate_content_item(
    session,
    store_id: int,
    template_code: str,
    scheduled_date: date | None = None,
    llm_client: LLMClient | None = None,
) -> ContentItem:
    template = load_template(template_code)
    values = auto_fill_variables(template_code, store_id, session)
    rendered = render_template(template, values)
    rendered = optimize_rendered_copy(rendered, values, llm_client)
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


def optimize_rendered_copy(rendered: dict, variables: dict, llm_client: LLMClient | None = None) -> dict:
    if llm_client is None:
        return rendered

    prompt = (
        "你是宠物门店的新媒体运营助手。请把下面的内容改写成自然、亲切、适合门店发布的中文文案，"
        "保留事实，不夸大效果，不制造焦虑。只输出 JSON，字段为 title、body、image_prompt。\n"
        f"门店：{variables.get('store_name')}\n"
        f"宠物：{variables.get('pet_name')}\n"
        f"品种：{variables.get('breed')}\n"
        f"服务：{variables.get('service_type')}\n"
        f"原标题：{rendered.get('title', '')}\n"
        f"原正文：{rendered.get('body', '')}\n"
        f"原图片提示：{rendered.get('image_prompt', '')}"
    )
    generated = llm_client.generate(prompt)
    optimized = _parse_copy_json(generated)
    if optimized is None:
        return rendered
    return {
        "title": optimized.get("title") or rendered.get("title", ""),
        "body": optimized.get("body") or rendered.get("body", ""),
        "hashtags": rendered.get("hashtags", []),
        "image_prompt": optimized.get("image_prompt") or rendered.get("image_prompt", ""),
    }


def _fallback_image_prompt(template_code: str, variables: dict) -> str:
    return f"Editable image prompt for {template_code}: {variables.get('pet_name')} at {variables.get('store_name')}"


def _parse_copy_json(text: str | None) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


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
