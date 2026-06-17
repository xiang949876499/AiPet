from agents.reminder import ReminderAgent


def run_reminder_scan(db_session, context: dict | None = None) -> dict:
    return ReminderAgent(db_session).execute(context or {})
