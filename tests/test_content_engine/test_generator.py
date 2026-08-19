def test_template_rendering_and_auto_fill_variables(db_session, sample_records):
    from content_engine.generator import auto_fill_variables, render_template

    values = auto_fill_variables("moments_before_after", sample_records["store"].id, db_session)
    rendered = render_template(
        {
            "title": "{store_name} grooming update",
            "body": "{pet_name} visited for {service_type}.",
            "hashtags": ["grooming"],
        },
        values,
    )

    assert sample_records["pet"].name in rendered["body"]
    assert "grooming" in rendered["hashtags"]


def test_generate_content_item_falls_back_to_image_prompt(db_session, sample_records):
    from app.models import ContentItem
    from content_engine.generator import generate_content_item

    item = generate_content_item(db_session, sample_records["store"].id, "moments_before_after")

    assert isinstance(item, ContentItem)
    assert item.image_prompt
    assert item.status == "draft"


def test_generate_content_item_uses_ai_copy_optimizer(db_session, sample_records):
    from content_engine.generator import generate_content_item
    from core.llm import LLMClient

    llm = LLMClient(
        generator=lambda prompt: (
            '{"title": "豆豆洗护焕新前后对比", '
            '"body": "豆豆这次洗护后清爽了不少，适合发一条温暖的到店案例。", '
            '"image_prompt": "豆豆洗护前后对比封面"}'
        )
    )

    item = generate_content_item(db_session, sample_records["store"].id, "moments_before_after", llm_client=llm)

    assert item.title == "豆豆洗护焕新前后对比"
    assert item.body == "豆豆这次洗护后清爽了不少，适合发一条温暖的到店案例。"
    assert item.image_prompt == "豆豆洗护前后对比封面"
