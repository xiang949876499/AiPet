def test_policy_allows_internal_staff_notification():
    from core.push_policy import PushPolicy

    assert PushPolicy().can_send_internal_staff(scene="repurchase_reminder") is True


def test_policy_blocks_medical_customer_content(sample_records):
    from core.push_policy import PushPolicy

    customer = sample_records["customer"]

    assert PushPolicy().validate_customer_content("建议用药治疗皮肤病", customer) == "medical_content_blocked"
