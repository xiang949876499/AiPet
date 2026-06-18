from datetime import datetime

from app.models import Staff, Store


def bind_wecom_staff(
    db_session,
    corp_id: str,
    userid: str,
    name: str = "",
    avatar: str = "",
) -> Staff:
    staff = db_session.query(Staff).filter_by(wecom_userid=userid).one_or_none()
    if staff is None:
        store = db_session.query(Store).order_by(Store.id.asc()).first()
        if store is None:
            raise ValueError("cannot bind wecom staff without a store")
        staff = Staff(
            store_id=store.id,
            name=name or f"企业微信成员 {userid}",
            role="店员",
            wecom_userid=userid,
        )
        db_session.add(staff)

    if name:
        staff.wecom_name = name
    if avatar:
        staff.wecom_avatar = avatar
    staff.wecom_corp_id = corp_id
    staff.wecom_bound_at = datetime.utcnow()
    db_session.commit()
    db_session.refresh(staff)
    return staff
