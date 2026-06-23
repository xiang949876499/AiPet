from datetime import datetime, timedelta


def test_trial_token_grants_growth_plan_for_14_days(tmp_path):
    from licensing.storage import LicenseStorage

    storage = LicenseStorage(tmp_path / "license.json")
    token = storage.create_trial_token(now=datetime(2026, 6, 22, 8, 0, 0))

    assert token["plan_code"] == "growth"
    assert token["is_trial"] is True
    assert token["token"].startswith("TRIAL-")
    assert storage.is_trial_token(token["token"]) is True
    assert storage.get_status(now=datetime(2026, 6, 23, 8, 0, 0))["mode"] == "active"


def test_plan_based_offline_grace_and_downgrade(tmp_path):
    from licensing.storage import LicenseStorage

    storage = LicenseStorage(tmp_path / "license.json")
    last_heartbeat = datetime(2026, 6, 1, 8, 0, 0)
    storage.save_token(
        token="LICENSE-1",
        plan_code="professional",
        expires_at=(last_heartbeat + timedelta(days=365)).isoformat(),
        last_heartbeat_at=last_heartbeat.isoformat(),
    )

    assert storage.is_grace_period_ok(now=last_heartbeat + timedelta(days=14)) is True

    status = storage.get_status(now=last_heartbeat + timedelta(days=16))
    assert status["mode"] == "downgraded"
    assert status["allowed_features"]["customer_files"] is True
    assert status["allowed_features"]["manual_script_generation"] is True
    assert status["allowed_features"]["auto_send"] is False
    assert status["allowed_features"]["dashboard_refresh"] is False
