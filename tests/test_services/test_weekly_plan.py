from datetime import date


def test_build_7_day_ops_plan_returns_sellable_weekly_plan(db_session, sample_records):
    from services.weekly_plan import build_7_day_ops_plan

    plan = build_7_day_ops_plan(db_session, sample_records["store"].id, start_date=date(2026, 6, 22))

    assert len(plan) == 7
    assert plan[0]["date"] == "2026-06-22"
    assert plan[0]["customer_focus"]
    assert plan[0]["suggested_action"]
    assert plan[0]["talking_point"]
    assert {item["channel"] for item in plan} >= {"朋友圈", "小红书", "短视频脚本"}
    assert any("豆豆" in item["customer_focus"] for item in plan)
