def test_content_agent_generates_daily_social_content(db_session, sample_records):
    from agents.content import ContentAgent
    from app.models import ContentItem
    from core.llm import LLMClient

    llm = LLMClient(generator=lambda prompt: "标题：夏日洗护提醒\n正文：给毛孩子安排一次清爽洗护，顺便检查脚底毛。")
    result = ContentAgent(db_session, llm=llm).execute({"store_id": sample_records["store"].id})

    assert result["created"] == 3
    items = db_session.query(ContentItem).order_by(ContentItem.channel.asc()).all()
    assert {item.channel for item in items} == {"朋友圈", "小红书", "短视频脚本"}
    assert all(item.status == "draft" for item in items)
    assert all("洗护" in item.body for item in items)


def test_content_agent_uses_fallback_without_llm(db_session, sample_records):
    from agents.content import ContentAgent
    from app.models import ContentItem

    result = ContentAgent(db_session).execute({"store_id": sample_records["store"].id})

    assert result["created"] == 3
    assert db_session.query(ContentItem).filter_by(channel="朋友圈").one().title == "今日客户维系提醒"
