def test_scheduler_job_runs_reminder_agent(db_session, sample_records):
    from core.scheduler import run_reminder_scan
    from app.models import FollowTask

    result = run_reminder_scan(db_session, {"store_id": sample_records["store"].id})

    assert result["created"] == 1
    assert db_session.query(FollowTask).count() == 1
