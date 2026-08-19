def test_advisor_prompt_uses_category_and_answer_sections(db_session):
    from agents.growth import AdvisorAgent
    from core.llm import LLMClient

    prompts = []
    llm = LLMClient(generator=lambda prompt: prompts.append(prompt) or "ok")

    result = AdvisorAgent(db_session, llm=llm).execute(
        {"question": "会员日怎么做？", "category": "活动策划"}
    )

    assert result == {"answer": "ok"}
    assert prompts
    prompt = prompts[0]
    assert "宠物门店运营专家助手" in prompt
    assert "场景分类：活动策划" in prompt
    assert "问题判断" in prompt
    assert "建议动作" in prompt
    assert "可复制话术" in prompt
    assert "注意事项" in prompt
    assert "不做医疗诊断" in prompt
    assert "店主问题：会员日怎么做？" in prompt


def test_advisor_fallback_gives_category_based_operations_answer(db_session):
    from agents.growth import AdvisorAgent

    result = AdvisorAgent(db_session).execute(
        {"question": "小红书怎么写种草文案？", "category": "内容营销"}
    )

    answer = result["answer"]
    assert "问题判断" in answer
    assert "内容营销" in answer
    assert "建议动作" in answer
    assert "可复制话术" in answer
    assert "注意事项" in answer
    assert "不承诺效果" in answer
    assert "专业兽医" not in answer


def test_advisor_rejects_medical_questions_before_llm(db_session):
    from agents.growth import AdvisorAgent
    from core.llm import LLMClient

    prompts = []
    llm = LLMClient(generator=lambda prompt: prompts.append(prompt) or "should not call")

    result = AdvisorAgent(db_session, llm=llm).execute({"question": "狗狗皮肤病怎么用药？"})

    answer = result["answer"]
    assert "专业兽医" in answer
    assert "日常护理参考" in answer
    assert prompts == []
