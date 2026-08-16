from datetime import date


def test_build_content_calendar_returns_seven_days(db_session, sample_records):
    from content_engine.calendar import build_content_calendar

    items = build_content_calendar(db_session, sample_records["store"].id, start=date(2026, 6, 22), days=7)

    assert len(items) == 7
    assert items[0]["date"] == "2026-06-22"
    assert items[0]["template_code"]
