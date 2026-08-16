from datetime import datetime, timedelta


def test_default_rules_include_ten_phase1_rules(db_session, sample_records):
    from app.models import OutreachRule
    from outreach.rules import DEFAULT_RULES, _ensure_default_rules

    _ensure_default_rules(db_session, sample_records["store"].id)

    assert len(DEFAULT_RULES) == 10
    assert db_session.query(OutreachRule).count() == 10


def test_scan_grooming_due_returns_decision_card(db_session, sample_records):
    from outreach.rules import scan_grooming_due

    hits = scan_grooming_due(db_session, sample_records["store"].id, now=datetime.utcnow())

    assert len(hits) == 1
    assert hits[0]["rule_code"] == "grooming_due"
    assert hits[0]["decision_card"]["trigger_rule"] == "grooming_due"
    assert hits[0]["decision_card"]["evidence"]["days_since"] >= 21


def test_scan_dormant_customers_uses_last_visit(db_session, sample_records):
    from outreach.rules import scan_dormant_customers

    sample_records["customer"].last_visit_time = datetime.utcnow() - timedelta(days=95)
    db_session.commit()

    hits = scan_dormant_customers(db_session, sample_records["store"].id)

    assert hits
    assert hits[0]["rule_code"] == "dormant_wake"
