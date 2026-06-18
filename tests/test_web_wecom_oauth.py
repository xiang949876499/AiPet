from fastapi.testclient import TestClient


class FakeWeComClient:
    corp_id = "corp-1"

    def get_oauth_userid(self, code: str):
        assert code == "login-code"
        return "wang"

    def get_user_detail(self, userid: str):
        assert userid == "wang"
        return {"name": "王店员", "avatar": "https://example.com/avatar.png"}


def test_wecom_oauth_start_redirects_to_enterprise_wechat(monkeypatch):
    monkeypatch.setenv("WECOM_CORP_ID", "corp-1")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000001")
    monkeypatch.setenv("WECOM_REDIRECT_URI", "https://aipet.example.com/wecom/oauth/callback")
    monkeypatch.setenv("WECOM_OAUTH_ENABLED", "true")

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/wecom/oauth/start", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://open.weixin.qq.com/connect/oauth2/authorize")
    assert "appid=corp-1" in response.headers["location"]
    assert "agentid=1000001" in response.headers["location"]


def test_wecom_oauth_callback_binds_staff_and_sets_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'wecom_oauth.db'}")
    monkeypatch.setenv("WECOM_CORP_ID", "corp-1")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000001")
    monkeypatch.setenv("WECOM_APP_SECRET", "secret")
    monkeypatch.setenv("WECOM_OAUTH_ENABLED", "true")

    from app.database import SessionLocal, init_db
    from app.models import Staff, Store
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        store = Store(name="豆豆宠物店")
        session.add(store)
        session.flush()
        session.add(Staff(store_id=store.id, name="小王", wecom_userid="wang"))
        session.commit()
    finally:
        session.close()

    client = TestClient(create_app(wecom_client_factory=lambda: FakeWeComClient()))
    response = client.get("/wecom/oauth/callback?code=login-code", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/"
    assert response.cookies.get("aipet_staff_id") is not None

    session = SessionLocal()
    try:
        staff = session.query(Staff).filter_by(wecom_userid="wang").one()
        assert staff.wecom_corp_id == "corp-1"
        assert staff.wecom_name == "王店员"
        assert staff.wecom_avatar == "https://example.com/avatar.png"
    finally:
        session.close()


def test_wecom_oauth_start_requires_feature_flag(monkeypatch):
    monkeypatch.setenv("WECOM_CORP_ID", "corp-1")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000001")
    monkeypatch.setenv("WECOM_REDIRECT_URI", "https://aipet.example.com/wecom/oauth/callback")
    monkeypatch.setenv("WECOM_OAUTH_ENABLED", "false")

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/wecom/oauth/start")

    assert response.status_code == 503
    assert response.json()["detail"] == "企业微信登录未启用"
