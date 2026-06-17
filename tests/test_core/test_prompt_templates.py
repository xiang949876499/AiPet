def test_washing_prompt_blocks_medical_advice():
    from core.prompt_templates import render_washing_reminder

    prompt = render_washing_reminder(
        customer_name="张姐",
        pet_name="豆豆",
        pet_type="狗",
        last_service_days=24,
        available_time="周三下午",
        promotion="老客小福利",
        note="皮肤红斑，想问用药",
    )

    assert "不要涉及医疗诊断" in prompt
    assert "不要建议用药" in prompt
    assert "豆豆" in prompt


def test_fallback_message_is_wechat_ready():
    from core.prompt_templates import fallback_message

    message = fallback_message("洗护提醒", "张姐", "豆豆")

    assert "豆豆" in message
    assert len(message) <= 120
    assert "预约" in message
