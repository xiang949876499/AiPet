def test_tiered_dashboard_returns_action_recommendations(db_session, sample_records):
    from analytics.dashboard import build_tiered_dashboard

    data = build_tiered_dashboard(db_session, sample_records["store"].id, "professional")

    assert data["tier"] == "professional"
    assert "metrics" in data
    assert data["action_recommendations"]
