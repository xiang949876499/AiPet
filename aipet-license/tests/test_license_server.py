from datetime import datetime, timedelta

from models import ActivationCode, License


def seed_license(session_factory, token="valid-token-123", plan_code="professional"):
    session = session_factory()
    try:
        code = ActivationCode(
            code="AIPET-PRO-TEST-CODE-001",
            plan_code=plan_code,
            valid_days=365,
            status="used",
        )
        session.add(code)
        session.flush()
        license_row = License(
            activation_code_id=code.id,
            token=token,
            plan_code=plan_code,
            store_name="Test Store",
            phone="",
            machine_id="machine-1",
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=30),
            last_heartbeat_at=datetime.utcnow() - timedelta(days=1),
        )
        session.add(license_row)
        session.commit()
        return license_row.id
    finally:
        session.close()


def test_activate_issues_license_token(client, license_db):
    session = license_db()
    try:
        session.add(ActivationCode(code="AIPET-GROWTH-ACTIVATE-001", plan_code="growth", valid_days=14))
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/activate",
        json={
            "activation_code": "AIPET-GROWTH-ACTIVATE-001",
            "store_name": "Happy Pets",
            "phone": "13800000000",
            "machine_id": "machine-1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token"].startswith("LICENSE-")
    assert data["plan_code"] == "growth"


def test_verify_valid_invalid_and_expired_tokens(client, license_db):
    license_id = seed_license(license_db)

    valid = client.post("/api/verify", json={"token": "valid-token-123", "machine_id": "machine-1"})
    assert valid.status_code == 200
    assert valid.json()["valid"] is True

    invalid = client.post("/api/verify", json={"token": "missing"})
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False

    session = license_db()
    try:
        license_row = session.get(License, license_id)
        license_row.expires_at = datetime.utcnow() - timedelta(days=1)
        session.commit()
    finally:
        session.close()

    expired = client.post("/api/verify", json={"token": "valid-token-123"})
    assert expired.status_code == 200
    assert expired.json() == {"valid": False, "reason": "expired"}


def test_heartbeat_updates_last_seen(client, license_db):
    seed_license(license_db)

    response = client.post("/api/heartbeat", json={"token": "valid-token-123", "machine_id": "machine-1"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    session = license_db()
    try:
        license_row = session.query(License).filter_by(token="valid-token-123").one()
        assert license_row.last_heartbeat_at > datetime.utcnow() - timedelta(minutes=1)
    finally:
        session.close()


def test_renew_extends_license_and_consumes_code(client, license_db):
    seed_license(license_db)
    session = license_db()
    try:
        session.add(ActivationCode(code="AIPET-PRO-RENEW-001", plan_code="professional", valid_days=365))
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/renew",
        json={"token": "valid-token-123", "renew_code": "AIPET-PRO-RENEW-001"},
    )

    assert response.status_code == 200
    assert response.json()["plan_code"] == "professional"
    session = license_db()
    try:
        license_row = session.query(License).filter_by(token="valid-token-123").one()
        renew_code = session.query(ActivationCode).filter_by(code="AIPET-PRO-RENEW-001").one()
        assert license_row.expires_at > datetime.utcnow() + timedelta(days=360)
        assert renew_code.status == "used"
    finally:
        session.close()


def test_upgrade_changes_plan_and_consumes_code(client, license_db):
    seed_license(license_db)
    session = license_db()
    try:
        session.add(ActivationCode(code="AIPET-GROWTH-UPGRADE-001", plan_code="growth", valid_days=365))
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/upgrade",
        json={"token": "valid-token-123", "upgrade_code": "AIPET-GROWTH-UPGRADE-001"},
    )

    assert response.status_code == 200
    assert response.json()["plan_code"] == "growth"
    session = license_db()
    try:
        license_row = session.query(License).filter_by(token="valid-token-123").one()
        upgrade_code = session.query(ActivationCode).filter_by(code="AIPET-GROWTH-UPGRADE-001").one()
        assert license_row.plan_code == "growth"
        assert upgrade_code.status == "used"
    finally:
        session.close()


def test_admin_page_and_unbind(client, license_db):
    license_id = seed_license(license_db)

    page = client.get("/admin")
    assert page.status_code == 200
    assert "Activation Records" in page.text

    unbind = client.post(f"/admin/licenses/{license_id}/unbind")
    assert unbind.status_code == 200
    assert unbind.json() == {"updated": True}
    session = license_db()
    try:
        license_row = session.get(License, license_id)
        assert license_row.machine_id is None
    finally:
        session.close()
