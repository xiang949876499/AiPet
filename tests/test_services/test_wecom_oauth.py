def test_bind_wecom_staff_updates_existing_staff(db_session, sample_records):
    from app.models import Staff
    from services.wecom_oauth import bind_wecom_staff

    staff = Staff(store_id=sample_records["store"].id, name="小王", wecom_userid="wang")
    db_session.add(staff)
    db_session.commit()

    bound = bind_wecom_staff(
        db_session,
        corp_id="corp-1",
        userid="wang",
        name="王店员",
        avatar="https://example.com/avatar.png",
    )

    assert bound.id == staff.id
    assert bound.wecom_corp_id == "corp-1"
    assert bound.wecom_name == "王店员"
    assert bound.wecom_avatar == "https://example.com/avatar.png"
    assert bound.wecom_bound_at is not None


def test_bind_wecom_staff_creates_staff_when_userid_is_new(db_session, sample_records):
    from services.wecom_oauth import bind_wecom_staff

    bound = bind_wecom_staff(db_session, corp_id="corp-1", userid="li", name="")

    assert bound.store_id == sample_records["store"].id
    assert bound.name == "企业微信成员 li"
    assert bound.wecom_userid == "li"
    assert bound.wecom_corp_id == "corp-1"
