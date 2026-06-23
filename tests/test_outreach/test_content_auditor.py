def test_content_auditor_blocks_sensitive_words():
    from outreach.content_auditor import audit_content

    result = audit_content("This is a guaranteed cure for skin disease")

    assert result["passed"] is False
    assert "guaranteed cure" in result["blocked_terms"]


def test_content_auditor_passes_safe_copy():
    from outreach.content_auditor import audit_content

    result = audit_content("Book a gentle grooming appointment this week.")

    assert result["passed"] is True
