from agents.review import ReviewAgent


def test_review_agent_generates_positive_review_reply(db_session):
    result = ReviewAgent(db_session).execute(
        {
            "scenario": "positive",
            "review_text": "洗得很干净，狗狗也不害怕。",
            "store_name": "豆豆宠物生活馆",
        }
    )

    assert result["scenario"] == "positive"
    assert "感谢" in result["reply"]
    assert "豆豆宠物生活馆" in result["reply"]


def test_review_agent_generates_careful_negative_review_reply(db_session):
    result = ReviewAgent(db_session).execute(
        {
            "scenario": "negative",
            "review_text": "洗得还行，但是等太久了。",
            "store_name": "豆豆宠物生活馆",
        }
    )

    assert result["scenario"] == "negative"
    assert "抱歉" in result["reply"]
    assert "复盘" in result["reply"]
    assert "自动发送" not in result["reply"]
