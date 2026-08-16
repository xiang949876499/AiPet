def test_seed_and_generate_reminders(tmp_path, monkeypatch):
    from app.database import init_db, SessionLocal
    from agents.reminder import ReminderAgent
    from seed_data import seed_demo_data

    db_path = tmp_path / "pet_agent.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
        result = ReminderAgent(session).execute({})
        assert result["created"] >= 1
    finally:
        session.close()
def test_full_phase1_daily_loop(db_session, sample_records):
    from analytics.dashboard import build_tiered_dashboard
    from app.models import OutreachLog
    from outreach.confirm_flow import confirm_message, get_pending_confirmations
    from outreach.engine import dispatch_outreach

    store_id = sample_records["store"].id
    result = dispatch_outreach(db_session, store_id, plan_code="professional")
    assert result["created"] >= 1

    pending = get_pending_confirmations(db_session, store_id)
    if pending:
        confirm_message(db_session, pending[0]["log_id"])

    log = db_session.query(OutreachLog).order_by(OutreachLog.id.asc()).first()
    assert log is not None
    log.status = "sent"
    log.service_within_7d = True
    log.attributed_revenue = 128
    db_session.commit()

    dashboard = build_tiered_dashboard(db_session, store_id, "professional")
    assert dashboard["metrics"]["attributed_revenue"] >= 128
    assert dashboard["action_recommendations"]
