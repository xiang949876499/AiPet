def test_register_outreach_jobs_adds_scan_and_send_jobs():
    from core.scheduler import register_outreach_jobs

    class Scheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, **kwargs):
            self.jobs.append((func, trigger, kwargs))

    scheduler = Scheduler()
    register_outreach_jobs(scheduler, session_factory=lambda: None)

    ids = {job[2]["id"] for job in scheduler.jobs}
    assert ids == {"outreach_scan", "outreach_send_morning", "outreach_send_afternoon", "outreach_send_evening"}
