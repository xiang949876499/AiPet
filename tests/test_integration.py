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
