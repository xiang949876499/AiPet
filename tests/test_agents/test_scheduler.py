from datetime import datetime, timedelta


def test_scheduler_agent_rejects_overlapping_appointment(db_session, sample_records):
    from agents.scheduler import SchedulerAgent

    agent = SchedulerAgent(db_session)
    start = datetime.utcnow() + timedelta(days=1)
    first = agent.create_appointment(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        service_type="洗护",
        start_time=start,
        duration_minutes=60,
    )
    second = agent.create_appointment(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        service_type="洗护",
        start_time=start + timedelta(minutes=30),
        duration_minutes=60,
    )

    assert first["created"] is True
    assert second["error"] == "appointment_conflict"
