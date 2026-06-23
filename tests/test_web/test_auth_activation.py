from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def test_dashboard_requires_local_login_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "true")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")
    monkeypatch.setenv("AIPET_ADMIN_PASSWORD", "secret")

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_local_login_sets_session_cookie_and_redirects(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'login.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "true")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")
    monkeypatch.setenv("AIPET_ADMIN_PASSWORD", "secret")

    from web.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/login",
        data={"password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert response.cookies.get("aipet_admin_session") is not None


def test_login_page_explains_secure_workbench_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'login-page.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "true")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")
    monkeypatch.setenv("AIPET_ADMIN_PASSWORD", "secret")

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/login?next=/reminders")

    assert response.status_code == 200
    assert "安全进入工作台" in response.text
    assert "一键启动后，用管理员密码进入后台" in response.text
    assert "先激活或试用" in response.text
    assert 'value="/reminders"' in response.text


def test_license_guard_redirects_to_activate_when_required(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'license-guard.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "true")
    monkeypatch.setenv("AIPET_LICENSE_FILE", str(tmp_path / "license.json"))

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/activate")


def test_activate_page_guides_first_run_trial_or_license(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'activate-page.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "true")
    monkeypatch.setenv("AIPET_LICENSE_FILE", str(tmp_path / "license.json"))

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/activate")

    assert response.status_code == 200
    assert "启动后第一步" in response.text
    assert "没有激活码也可以先开启本机试用" in response.text
    assert "试用不会自动发送外部客户消息" in response.text
    assert "开启 14 天试用" in response.text


def test_activate_page_starts_trial_and_unlocks_dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'trial.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "true")
    monkeypatch.setenv("AIPET_LICENSE_FILE", str(tmp_path / "license.json"))

    from web.app import create_app

    client = TestClient(create_app())
    response = client.post("/activate/trial", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert response.cookies.get("aipet_license_unlocked") == "1"

    unlocked = client.get("/")
    assert unlocked.status_code == 200
    assert "AI 运营工作台" in unlocked.text


def test_expired_license_redirects_to_activate(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'expired.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "true")
    monkeypatch.setenv("AIPET_LICENSE_FILE", str(tmp_path / "license.json"))

    from licensing.storage import LicenseStorage

    LicenseStorage(tmp_path / "license.json").save_token(
        token="LICENSE-old",
        plan_code="professional",
        expires_at=(datetime.utcnow() - timedelta(days=1)).isoformat(),
        last_heartbeat_at=(datetime.utcnow() - timedelta(days=10)).isoformat(),
    )

    from web.app import create_app

    client = TestClient(create_app())
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/activate?reason=expired"


def test_dashboard_includes_first_run_guide(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'first-run.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "首次使用引导" in response.text
    assert "导入客户数据" in response.text
    assert "检查待跟进提醒" in response.text
    assert "生成今日内容" in response.text
